"""Director / state machine (code, no model). See docs/STATE_MACHINE.md."""
import random
import re
from dataclasses import dataclass, field
from . import constants as C

MAX_STAGE = 6
MIN_DWELL = {1: 3, 2: 4, 3: 3, 4: 3, 5: 4}
ADV_THRESHOLD = {1: 0.35, 2: 0.4, 3: 0.45, 4: 0.5, 5: 0.6}
ONSET_MIN_TURNS = 14        # stage 6 needs this many user turns, receptiveness >= 0.6, no resistance
ONSET_MAX_SHARE = 0.25      # stage 6 may occupy at most this share of turns
ONSET_MIN_LEN = 4.5         # ...and the user must be genuinely engaged: EMA of words per message
ONSET_MIN_DISCLOSURES = 2   # ...and have volunteered personal information several times
STEP = 0.05
INTENT = {
    1: "Come across as relatable: share small personal details that mirror their interests.",
    2: "Show warm interest; ask open questions about their life and feelings to learn what they need.",
    3: "Casually learn about their day-to-day life: how they spend evenings and weekends, and who they usually spend time with.",
    4: "Offer something appealing: compliments, attention, or small shared plans.",
    5: "Deepen the bond: express closeness and a special connection between you two.",
    6: "Let the warmth turn lightly romantic: compliment their personality or humour, say you enjoy talking to them, and ask gentle, non-explicit questions about relationships and feelings. Stay light, never explicit.",
}
SECONDARY_EASE = "Ease off and keep it light and friendly."

_NEUTRALISE = re.compile(r"\b(no worries|no problem|no offense|don'?t know|dont know|can'?t stop (?:laughing|smiling)|not bad)\b")
_RES = re.compile(r"\b(no|nope|nah|stop|don'?t|dont|why (?:do|are) you|weird|creepy|uncomfortable|not comfortable|leave me|"
                  r"none of your|i don'?t want|suspicious|who are you really|block|rather not|prefer not|too personal|leave it|not sure i want)\b")
_WARM = re.compile(r"\b(thanks|thank you|haha+|lol|love|nice|great|awesome|cool|sweet|glad|happy|same|me too|"
                   r"yes|yeah|sure)\b|[:;]-?[)D]|\U0001F600|\U0001F60A|\u2764")
_BOUNDARY = re.compile(r"\b(i have a (?:boyfriend|girlfriend|partner|husband|wife)|i'?m (?:in a relationship|married|taken|engaged)|i'?m with someone)\b")
# disclosure categories (the director note carries only these labels, never raw user text)
_DISC = {
    "work or study": re.compile(r"\b(i work|my job|i study|my (?:school|uni|university|college|boss)|i'?m (?:a|an) \w+)\b"),
    "family": re.compile(r"\bmy (?:mum|mom|dad|family|sister|brother|parents)\b"),
    "friends or partner": re.compile(r"\bmy (?:friends?|girlfriend|boyfriend|roommate|flatmate|partner)\b"),
    "living situation": re.compile(r"\b(i live|my (?:flat|house|apartment|place)|i moved|i'?m new)\b"),
    "feelings": re.compile(r"\bi (?:feel|felt)\b|\bi'?m (?:lonely|sad|bored|stressed|tired|anxious|happy|excited)\b"),
    "interests": re.compile(r"\bi (?:love|like|enjoy|play|listen|watch|read)\b"),
}


def score_user(text: str) -> dict:
    t = text.lower().strip()
    cats = [k for k, rx in _DISC.items() if rx.search(t)]
    words = len(t.split())
    res = 1.0 if _RES.search(_NEUTRALISE.sub(" ", t)) else 0.0
    return {
        "resistance": res,
        "boundary": 1.0 if _BOUNDARY.search(t) else 0.0,
        "warmth": min(1.0, 0.5 * len(_WARM.findall(t)) + (0.3 if "?" in t else 0.0)),
        "disclosure": min(1.0, 0.5 * len(cats)),
        "categories": cats,
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
    onset_turns: int = 0
    len_ema: float = 3.0
    disclosures: int = 0


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


class Director:
    def __init__(self, bias: dict, rng: random.Random | None = None, advance_p: float = 0.6, allow_onset: bool = True):
        self.rng = rng or random.Random()
        self.p = advance_p
        self.max_stage = MAX_STAGE if (allow_onset and C.ALLOW_ONSET) else 5
        self.s = State(offender_type=bias["offender_type"], register=bias["register"])

    def observe(self, user_text: str, pushed: bool = False) -> dict:
        """Update state from a user message. `pushed`: the user tried to push past the limits; the message carries no
        receptiveness or disclosure signal. Returns the signal dict."""
        s, sig = self.s, score_user(user_text)
        if sig["boundary"] and s.stage >= 5:
            sig["resistance"] = 1.0                       # "I have a boyfriend" at the intimate stages = a boundary
        if pushed:
            sig = {**sig, "warmth": 0.0, "disclosure": 0.0, "categories": [], "resistance": 0.0}
        raw = 0.5 * sig["warmth"] + 0.4 * sig["disclosure"] - 0.6 * sig["resistance"] - 0.1 * sig["short"]
        s.receptiveness = _clip(0.6 * s.receptiveness + 0.4 * _clip(0.5 + raw))
        s.resistance_streak = s.resistance_streak + 1 if sig["resistance"] else 0
        if sig["resistance"]:
            s.ease_turns = 2
        s.len_ema = 0.7 * s.len_ema + 0.3 * len(user_text.split())
        if sig["disclosure"] > 0:
            s.disclosures += 1
            s.facts.append(user_text.strip()[:80])
            s.facts = s.facts[-6:]
        # scalars (bounded steps)
        if s.stage >= 5 and s.receptiveness > 0.55:
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
        share = s.onset_turns / max(1, s.turn)
        if s.stage == 6 and (sig["resistance"] or s.receptiveness < 0.45 or share > ONSET_MAX_SHARE or s.len_ema < 4):
            s.stage, s.dwell, s.cooldown = 5, 0, 2          # drop out of onset immediately; fresh dwell needed to re-enter
        elif (s.resistance_streak >= 2 or s.receptiveness < 0.2) and s.stage > 1:
            s.stage -= 1
            s.dwell = 0
            s.cooldown = 2
        elif (s.stage < self.max_stage and s.dwell >= MIN_DWELL[s.stage] and not s.cooldown
              and s.receptiveness >= ADV_THRESHOLD[s.stage] and not sig["resistance"]
              and (s.stage < 5 or (s.turn >= ONSET_MIN_TURNS and s.resistance_streak == 0 and share < ONSET_MAX_SHARE
                           and s.len_ema >= ONSET_MIN_LEN and s.disclosures >= ONSET_MIN_DISCLOSURES))
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
            parts.append("They have mentioned their " + ", ".join(s.facts[-3:]) + "; pick up on it naturally.")
        if s.openers:
            parts.append("Do not start your message like these: " + " | ".join('"' + o + '"' for o in s.openers[-3:]) + ".")
        return " ".join(parts)

    def hints(self) -> tuple[str, str]:
        """Plain tone words for the prompt. 'Controlling' means taking the lead, never pressure (prohibited by the ceiling)."""
        s = self.s
        reg = "easygoing, follows their lead" if s.register < 0.33 else "takes the lead and steers the conversation, but is never pushy" if s.register > 0.66 else "friendly and a little persistent about keeping the chat going"
        off = "warm and interested in getting close" if (s.offender_type < 0.5 or s.stage < 5) else "warm, lightly flirtatious" if s.offender_type <= 0.66 else "openly flirtatious but never explicit"
        return reg, off

    def commit(self, reply: str):
        """Record the attacker turn (call after a reply is accepted)."""
        s = self.s
        s.history.append(self.tag())
        if s.stage == 6:
            s.onset_turns += 1
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
