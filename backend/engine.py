"""Turn pipeline. Safeguards are code; the model is untrusted for the limits (D-005)."""
import asyncio
import random
import re
import time
import uuid
from . import constants as C
from .antirepeat import too_repetitive
from .director import Director
from .filters import (distress_hit, humanize, is_stop, limit_push, looks_german, normalize, output_violation, shape, user_states_minor)
from .prompt import build_messages

GENERIC_FALLBACKS = ["haha sorry, got distracted for a second. what were you saying?", "ok random thought, what's the best thing you ate this week?",
                     "sorry, lost my train of thought there. how's your day been?", "wait, tell me something i don't know about you",
                     "ha, you've got me thinking now. go on?", "my phone died for a sec, i'm back. what did i miss?"]
FALLBACK_LINES = GENERIC_FALLBACKS          # kept for tests: every line is pre-checked against the filter
DEFLECT_NOTE = ("[DIRECTOR NOTE] Write one short, natural text that smoothly moves on to something light: a detail from your own day or "
                "one of your interests. Keep it friendly and plain.")
TIMEOUT_GRACE_S = 90                        # a reply already being written is delivered before a time-out closes the chat
CORRECTIONS = {"identity_request": "Do not ask for an exact address, phone number, email or full name.",
               "pressure_or_threat": "No threats or blackmail; stay friendly and charming.",
               "explicit": "Keep it clean; no sexual wording.",
               "roleplay": "Write plain text only: no actions, no asterisks, no suggestive emoji.",
               "language": "Write in English only.", "meta_commentary": "Stay fully in character; do not comment on the chat itself.",
               "money": "Do not mention money or payments.", "minor_reference": "Do not mention anyone's age.",
               "youthful_reference": "Do not mention age or youthfulness.", "self_harm": "Be supportive; say nothing harmful.",
               "stock_phrase": "Sound like a real person texting: casual and specific, no customer-service phrases.",
               "copied_example": "Write something new in your own words; do not reuse the example phrases."}


class BusyError(Exception):
    pass


def trim_to_sentence(text: str) -> str:
    """If generation was cut at max_tokens mid-sentence, cut back to the last complete sentence."""
    t = text.strip()
    if not t or t[-1] in ".!?)\"'\u2026" or re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]\s*$", t):
        return t
    m = list(re.finditer(r"[.!?](?=\s|$)", t))
    return t[: m[-1].end()].strip() if m else t


SUPPORT_REASONS = {"distress", "user_minor"}
CLOSE_REASONS = {"stop", "timeout", "distress", "user_minor"}     # the persona and the filters never end a chat (D-033)


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
                          "pushes": 0, "used_fb": [], "task": None, "busy": False}
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
        if s["ended_at"] is None and self.remaining(sid) <= 0 and self._past_grace(sid, s["started_at"]):
            self.end(sid, "timeout")
        return self.store.session(sid)["ended_at"] is not None

    def _past_grace(self, sid, started_at) -> bool:
        live = self.live.get(sid)
        busy = bool(live and live["busy"])
        return (not busy) or self.clock() - started_at >= self.limit_s + TIMEOUT_GRACE_S

    def sweep(self) -> int:
        """Server-side clock: end every expired open session, no client needed."""
        n = 0
        for r in self.store.open_sessions():
            if self.clock() - r["started_at"] >= self.limit_s and self._past_grace(r["sid"], r["started_at"]):
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
        if user_states_minor(text):          # hard line: the persona never talks on with someone who says they are under 18
            return self.end(sid, "user_minor", "user age <18 or age-gate contradiction")
        if distress_hit(text):               # text is not stored or sent to the model
            if self.cfg.get("safeguards", {}).get("distress_mode", "pause") == "end":
                return self.end(sid, "distress", "distress rule hit")
            self.store.event(sid, "distress_pause", "support card shown; chat paused, participant may continue")
            return {"ended": False, "paused": True, "support": True, "messages": [], "remaining": self.remaining(sid)}
        live = self.live[sid]
        if live["busy"]:
            raise BusyError(sid)
        extra, pushed = "", False
        if limit_push(text):                 # never ends the chat: the persona just deflects in character
            pushed = True
            live["pushes"] += 1
            self.store.event(sid, "limit_push", str(live["pushes"]))
            extra = "Do not mirror or escalate what they said; deflect naturally in character and move the chat somewhere lighter."
        d = live["dir"]
        sig = d.observe(text, pushed=pushed)
        self.store.add_turn(sid, "user", text, self.clock(),
                            meta={"signals": {k: v for k, v in sig.items() if k != "categories"}, "topics": sig.get("categories", []),
                                  "pushed": pushed, "german": looks_german(text)})
        plan = d.prepare(german=looks_german(text), connection=self.personas[self.store.session(sid)["persona_id"]].get("connection"))
        persona = self.personas[self.store.session(sid)["persona_id"]]
        live["busy"] = True
        task = asyncio.ensure_future(self._generate(sid, persona, d, extra))
        live["task"] = task
        try:
            reply = await task
        except asyncio.CancelledError:
            if self.store.session(sid)["ended_at"] is not None:        # Stop / timeout cancelled the generation
                return self.end(sid, self.store.session(sid)["end_reason"])
            task.cancel(); raise                                       # client disconnected: do NOT end the session
        finally:
            live["busy"] = False
        if self.store.session(sid)["ended_at"] is not None:   # Stop/timeout won the race: discard reply
            return self.end(sid, self.store.session(sid)["end_reason"])
        p, q = d.tag()
        st = d.s
        d.commit(reply)
        self.store.add_turn(sid, "attacker", reply, self.clock(), p, q,
                            meta={"stage": plan["stage"], "move": plan["move"], "tone": list(plan["tone"]), "note": plan["note"],
                                  "receptiveness": round(st.receptiveness, 2), "offender_type": round(st.offender_type, 2),
                                  "register": round(st.register, 2), "resistance_streak": st.resistance_streak})
        self.store.snapshot(sid, d.s)
        return {"ended": False, "messages": self._split(reply), "remaining": self.remaining(sid)}

    @staticmethod
    def _copied_example(persona, cand) -> bool:
        flat = re.sub(r"[^a-z0-9 ]", "", normalize(cand))
        return any(len(x) >= 12 and re.sub(r"[^a-z0-9 ]", "", normalize(x)) in flat for x in persona.get("style_samples", []))

    async def _candidate(self, sid, persona, messages, boost=0.0, d=None):
        plan = (d.plan if d else {}) or {}
        raw = await self.llm.generate(messages, penalty_boost=boost, max_tokens=plan.get("max_tokens"))
        if getattr(raw, "finish", None) == "length":                      # only repair replies the token limit cut off
            raw = trim_to_sentence(raw)
        cand = humanize(raw, persona["voice"])
        copied = self._copied_example(persona, cand)                      # check the full text before it is shaped down
        if d is not None and plan:
            cand = shape(cand, plan.get("max_sentences", 3), avoid_question=d.s.last_q or (bool(d.s.q_hist) and sum(d.s.q_hist) / len(d.s.q_hist) > 0.5))
        why = output_violation(cand) or ("copied_example" if copied else None)
        return cand, why

    async def _generate(self, sid, persona, d, extra):
        """Always returns a reply: filtered retries with rule-specific corrections, then an in-character deflection, then a
        persona-specific line. A filter problem never ends the chat (D-033)."""
        turns = self.store.turns(sid)
        recent = [t["text"] for t in turns if t["role"] == "attacker"]       # whole history: never repeat an earlier message
        boost, note, reply = 0.0, extra, None
        for retry in range(C.MAX_ANTIREPEAT_RETRIES + 1):
            reply = None
            for _ in range(C.MAX_FILTER_REGENERATIONS + 1):
                cand, why = await self._candidate(sid, persona, build_messages(persona, d, turns, note), boost, d)
                if why:
                    self.store.event(sid, "filter_hit", f"{why}: {cand[:300]}")   # blocked text logged for the researcher
                    note = (extra + " " + CORRECTIONS.get(why, "")).strip()
                    continue
                reply = cand
                break
            if reply is None:
                return await self._deflect(sid, persona, d, turns)
            if not too_repetitive(reply.replace("||", " "), recent) or retry == C.MAX_ANTIREPEAT_RETRIES:
                return reply
            self.store.event(sid, "antirepeat_retry", str(retry + 1))
            boost += 0.1
            note = (extra + " Vary phrasing and topic.").strip()
        return reply

    async def _deflect(self, sid, persona, d, turns):
        for _ in range(3):
            cand, why = await self._candidate(sid, persona, build_messages(persona, d, turns, note_override=DEFLECT_NOTE), 0.2)
            if not why:
                self.store.event(sid, "deflection_generated", cand[:200])
                return cand
        pool = [humanize(x, persona["voice"]) for x in persona.get("fallback_lines", []) + GENERIC_FALLBACKS]
        pool = [x for x in pool if output_violation(x) is None]
        used = self.live[sid]["used_fb"]
        fresh = [x for x in pool if x not in used] or (used.clear() or pool)
        line = self.rng.choice(fresh)
        used.append(line)
        self.store.event(sid, "fallback_used", "filter exhausted; persona line sent")
        return line

    def _split(self, reply: str) -> list[dict]:
        parts = [p.strip() for p in reply.split("||") if p.strip()][:3] or [reply]
        if len(parts) == 1 and len(reply) > 60 and self.rng.random() < 0.3 and ". " in reply:
            a, b = reply.split(". ", 1)
            parts = [a + ".", b]
        return [{"text": t, "delay_ms": int(min(4000, 500 + 45 * len(t)))} for t in parts]
