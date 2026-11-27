"""Turn pipeline. Safeguards are code; the model is untrusted for the limits (D-005)."""
import asyncio
import random
import time
import uuid
from . import constants as C
from .antirepeat import too_repetitive
from .director import Director
from .filters import (distress_hit, is_stop, limit_push, output_violation, user_states_minor)
from .prompt import build_messages

SUPPORT_REASONS = {"distress", "user_minor"}
CLOSE_REASONS = {"stop", "timeout", "distress", "user_minor", "limit_pushes", "filter_exhausted"}


class Engine:
    def __init__(self, cfg, personas, store, llm, clock=time.time, rng=None):
        self.cfg, self.personas, self.store, self.llm = cfg, personas, store, llm
        self.clock, self.rng = clock, rng or random.Random()
        self.limit_s = cfg["limits"]["max_session_seconds"]
        self.live: dict[str, dict] = {}

    # --- lifecycle -------------------------------------------------------
    def start_session(self, pid, persona_id, consent: bool, age_confirmed: bool, consent_version="v1"):
        if not (consent and age_confirmed):
            raise PermissionError("consent and 18+ confirmation are required")
        if persona_id not in self.personas:
            raise KeyError(persona_id)
        sid = uuid.uuid4().hex[:12]
        now = self.clock()
        self.store.add_participant(pid, consent_version, age_confirmed, now)
        self.store.add_session(sid, pid, persona_id, self.cfg["config_hash"], now)
        p = self.personas[persona_id]
        self.live[sid] = {"dir": Director(p["bias"], self.rng, allow_onset=self.cfg.get("safeguards", {}).get("allow_onset", True)),
                          "pushes": 0, "task": None}
        return {"sid": sid, "context_line": p["context_line"], "limit_seconds": self.limit_s}

    def remaining(self, sid) -> int:
        s = self.store.session(sid)
        return max(0, int(self.limit_s - (self.clock() - s["started_at"])))

    def end(self, sid, reason, detail="") -> dict:
        first = self.store.end_session(sid, reason, self.clock())
        live = self.live.get(sid)
        if live and live["task"] and not live["task"].done():
            live["task"].cancel()          # cancel in-flight generation
        if first and detail:
            self.store.event(sid, reason, detail)
        s = self.store.session(sid)
        return {"ended": True, "reason": s["end_reason"], "support": s["end_reason"] in SUPPORT_REASONS, "messages": []}

    def enforce_time(self, sid) -> bool:
        """End the session if its time is up (idempotent). Returns True if it is ended."""
        s = self.store.session(sid)
        if s["ended_at"] is None and self.remaining(sid) <= 0:
            self.end(sid, "timeout")
        return self.store.session(sid)["ended_at"] is not None

    def sweep(self) -> int:
        """Server-side clock: end every expired open session, no client needed."""
        n = 0
        for r in self.store.open_sessions():
            if self.clock() - r["started_at"] >= self.limit_s:
                self.end(r["sid"], "timeout"); n += 1
        return n

    def stop(self, sid) -> dict:
        """Never touches the LLM: always instant."""
        return self.end(sid, "stop")

    # --- turn ------------------------------------------------------------
    async def handle_message(self, sid, text: str) -> dict:
        s = self.store.session(sid)
        if s is None:
            raise KeyError(sid)
        if s["ended_at"] is not None:
            return self.end(sid, s["end_reason"])
        if self.remaining(sid) <= 0:
            return self.end(sid, "timeout")
        text = text.strip()[:1000]
        if is_stop(text):
            self.store.add_turn(sid, "user", text, self.clock())
            return self.end(sid, "stop")
        if user_states_minor(text):          # text never stored or sent to the model
            return self.end(sid, "user_minor", "user age <18 or age-gate contradiction")
        if distress_hit(text):
            return self.end(sid, "distress", "distress rule hit")
        live = self.live[sid]
        extra = ""
        if limit_push(text):
            live["pushes"] += 1
            self.store.event(sid, "limit_push", str(live["pushes"]))
            if live["pushes"] >= C.MAX_LIMIT_PUSHES:
                return self.end(sid, "limit_pushes", "repeated attempts to push past limits")
            extra = "Do not mirror or escalate what they said; deflect naturally in character and change the subject."
        self.store.add_turn(sid, "user", text, self.clock())
        d = live["dir"]
        d.observe(text)
        persona = self.personas[self.store.session(sid)["persona_id"]]
        task = asyncio.ensure_future(self._generate(sid, persona, d, extra))
        live["task"] = task
        try:
            reply = await task
        except asyncio.CancelledError:
            return self.end(sid, self.store.session(sid)["end_reason"] or "stop")
        if reply is None:
            return self.end(sid, "filter_exhausted", "output filter exhausted retries; flagged")
        if self.store.session(sid)["ended_at"] is not None:   # Stop/timeout won the race: discard reply
            return self.end(sid, self.store.session(sid)["end_reason"])
        p, q = d.tag()
        d.commit(reply)
        self.store.add_turn(sid, "attacker", reply, self.clock(), p, q)
        self.store.snapshot(sid, d.s)
        return {"ended": False, "messages": self._split(reply), "remaining": self.remaining(sid)}

    async def _generate(self, sid, persona, d, extra):
        turns = self.store.turns(sid)
        recent = [t["text"] for t in turns if t["role"] == "attacker"][-6:]
        boost, note = 0.0, extra
        for retry in range(C.MAX_ANTIREPEAT_RETRIES + 1):
            reply = None
            for _ in range(C.MAX_FILTER_REGENERATIONS + 1):
                cand = await self.llm.generate(build_messages(persona, d, turns, note), penalty_boost=boost)
                why = output_violation(cand)
                if why:
                    self.store.event(sid, "filter_hit", f"{why}: {cand[:300]}")   # blocked text logged for the researcher
                    continue
                reply = cand
                break
            if reply is None:
                return None
            if not too_repetitive(reply, recent) or retry == C.MAX_ANTIREPEAT_RETRIES:
                return reply
            self.store.event(sid, "antirepeat_retry", str(retry + 1))
            boost += 0.1
            note = (extra + " Vary phrasing and topic.").strip()
        return reply

    def _split(self, reply: str) -> list[dict]:
        parts = [reply]
        if len(reply) > 60 and self.rng.random() < 0.3 and ". " in reply:
            a, b = reply.split(". ", 1)
            parts = [a + ".", b]
        return [{"text": t, "delay_ms": int(min(4000, 500 + 45 * len(t)))} for t in parts]
