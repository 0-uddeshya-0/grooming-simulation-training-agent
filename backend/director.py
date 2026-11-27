"""Director / state machine (code, no model). See docs/STATE_MACHINE.md."""
import random
import re
from dataclasses import dataclass, field
from . import constants as C

MAX_STAGE = 5   # stage 6 not built (D-012)
MIN_DWELL = {1: 3, 2: 4, 3: 3, 4: 3, 5: 4}
ADV_THRESHOLD = {1: 0.35, 2: 0.4, 3: 0.45, 4: 0.5, 5: 0.6}
STEP = 0.05
INTENT = {
    1: "Come across as relatable: share small personal details that mirror their interests.",
    2: "Show warm interest; ask open questions about their life and feelings to learn what they need.",
    3: "Casually find out how much privacy and oversight they have in their day-to-day life.",
    4: "Offer something appealing: compliments, attention, or small shared plans.",
    5: "Deepen the bond: express closeness and a special connection between you two.",
}
SECONDARY_EASE = "Ease off and keep it light and friendly."

_RES = re.compile(r"\b(no|nope|stop|don'?t|dont|why (?:do|are) you|weird|creepy|uncomfortable|not comfortable|leave me|"
                  r"none of your|i don'?t want|suspicious|who are you really|block)\b")
_WARM = re.compile(r"\b(thanks|thank you|haha+|lol|love|nice|great|awesome|cool|sweet|glad|happy|same|me too|"
                   r"yes|yeah|sure)\b|[:;]-?[)D]|\U0001F600|\U0001F60A|❤")
_DISC = re.compile(r"\b(i live|i work|i study|my (?:mum|mom|dad|friend|friends|job|school|uni|name|girlfriend|boyfriend|"
                   r"family|roommate|flat|house)|i feel|i'?m (?:lonely|sad|bored|stressed|tired|new)|i have|i don'?t have)\b")


def score_user(text: str) -> dict:
    t = text.lower().strip()
    words = len(t.split())
    return {
        "resistance": 1.0 if _RES.search(t) else 0.0,
        "warmth": min(1.0, 0.5 * len(_WARM.findall(t)) + (0.3 if "?" in t else 0.0)),
        "disclosure": min(1.0, 0.5 * len(_DISC.findall(t)) + (0.2 if words > 12 else 0.0)),
        "short": 1.0 if words <= 3 else 0.0,
    }


@dataclass
class State:
    turn: int = 0
    stage: int = 1
    dwell: int = 0
    receptiveness: float = 0.5
    resistance_streak: int = 0
    cooldown: int = 0
    offender_type: float = 0.4
    register: float = 0.3
    ease_turns: int = 0
    facts: list = field(default_factory=list)
    history: list = field(default_factory=list)   # [(primary_idx, secondary_idx|None)]
    openers: list = field(default_factory=list)


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


class Director:
    def __init__(self, bias: dict, rng: random.Random | None = None, advance_p: float = 0.6):
        self.rng = rng or random.Random()
        self.p = advance_p
        self.s = State(offender_type=bias["offender_type"], register=bias["register"])

    def observe(self, user_text: str) -> dict:
        """Update state from a user message. Returns the signal dict."""
        s, sig = self.s, score_user(user_text)
        raw = 0.5 * sig["warmth"] + 0.4 * sig["disclosure"] - 0.6 * sig["resistance"] - 0.1 * sig["short"]
        s.receptiveness = _clip(0.6 * s.receptiveness + 0.4 * _clip(0.5 + raw))
        s.resistance_streak = s.resistance_streak + 1 if sig["resistance"] else 0
        if sig["resistance"]:
            s.ease_turns = 2
        if sig["disclosure"] > 0:
            s.facts.append(user_text.strip()[:80])
            s.facts = s.facts[-6:]
        # scalars (bounded steps)
        if s.stage >= 4 and s.receptiveness > 0.55:
            s.offender_type = _clip(s.offender_type + STEP)
        elif sig["disclosure"] > 0 and sig["warmth"] > 0:
            s.offender_type = _clip(s.offender_type - STEP)
        if sig["resistance"]:
            s.register = _clip(s.register + STEP)
        elif s.receptiveness > 0.55:
            s.register = _clip(s.register - STEP)
        # stage transition: stay / +1 / -1 only
        s.turn += 1
        s.dwell += 1
        if s.cooldown:
            s.cooldown -= 1
        if (s.resistance_streak >= 2 or s.receptiveness < 0.2) and s.stage > 1:
            s.stage -= 1
            s.dwell = 0
            s.cooldown = 2
        elif (s.stage < MAX_STAGE and s.dwell >= MIN_DWELL[s.stage] and not s.cooldown
              and s.receptiveness >= ADV_THRESHOLD[s.stage] and not sig["resistance"]
              and self.rng.random() < self.p):
            s.stage += 1
            s.dwell = 0
        return sig

    def tag(self) -> tuple[int, int | None]:
        s = self.s
        sec = 2 if (s.ease_turns and s.stage != 2) else None   # ease-off = soft rapport
        return s.stage - 1, (sec - 1 if sec else None)

    def note(self) -> str:
        s = self.s
        parts = [INTENT[s.stage]]
        if s.ease_turns:
            parts.append(SECONDARY_EASE)
        if s.facts:
            parts.append("They have shared: " + "; ".join(s.facts[-3:]) + ".")
        if s.openers:
            parts.append("Avoid starting like: " + " / ".join(s.openers[-3:]) + ".")
        return " ".join(parts)

    def hints(self) -> tuple[str, str]:
        s = self.s
        reg = "passive and easygoing" if s.register < 0.33 else "pushy and insistent" if s.register > 0.66 else "balanced, gently persistent"
        off = "seeks emotional closeness" if s.offender_type < 0.33 else "increasingly flirtatious" if s.offender_type > 0.66 else "mix of closeness and flirtiness"
        return reg, off

    def commit(self, reply: str):
        """Record the attacker turn (call after a reply is accepted)."""
        s = self.s
        s.history.append(self.tag())
        s.openers.append(" ".join(reply.split()[:3]))
        s.openers = s.openers[-6:]
        if s.ease_turns:
            s.ease_turns -= 1


def exposure(history: list) -> dict:
    n = len(history) or 1
    prim = {i: 0 for i in range(6)}
    sec = {i: 0 for i in range(6)}
    for p, q in history:
        prim[p] += 1
        if q is not None:
            sec[q] += 1
    return {C.STRATEGIES[i]: {"primary_pct": round(100 * prim[i] / n, 1), "secondary_pct": round(100 * sec[i] / n, 1)}
            for i in range(6)}
