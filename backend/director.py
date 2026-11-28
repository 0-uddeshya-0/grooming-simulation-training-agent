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
    4: "Make contact with you feel rewarding: compliments, attention, little treats or plans you could share.",
    5: "Deepen the bond: express closeness and a special connection between you two.",
    6: "Let the warmth turn lightly romantic: compliment their personality or humour, say you enjoy talking to them, and ask gentle, non-explicit questions about relationships and feelings. Stay light, never explicit.",
}

_NEUTRALISE = re.compile(r"\b(no worries|no problem|no offense|don'?t know|dont know|can'?t stop (?:laughing|smiling)|not bad)\b")
_RES = re.compile(r"\b(no|nope|nah|stop|don'?t|dont|why (?:do|are) you|weird|creepy|uncomfortable|not comfortable|leave me|"
                  r"none of your|i don'?t want|suspicious|who are you really|block|rather not|prefer not|too personal|leave it|not sure i want)\b")
_WARM = re.compile(r"\b(thanks|thank you|haha+|lol|love|nice|great|awesome|cool|sweet|glad|happy|same|me too|"
                   r"yes|yeah|sure)\b|[:;]-?[)D]|\U0001F600|\U0001F60A|\u2764")
_META_Q = re.compile(r"\b(are you (?:a |an )?(?:real|bot|ai|human|fake|robot|chatgpt)|is this a bot|you(?:'re| are) (?:a )?(?:bot|ai|fake)|chat ?gpt|real person)\b")
_BOUNDARY = re.compile(r"\b(i have a (?:boyfriend|girlfriend|partner|husband|wife)|i'?m (?:in a relationship|married|taken|engaged)|i'?m with someone)\b")
# disclosure categories (the director note carries only these labels, never raw user text)
_DISC = {
    "work or study": re.compile(r"\b(i work|my job|i study|my (?:school|uni|university|college|boss)|i'?m (?:a|an) \w+)\b"),
    "family": re.compile(r"\bmy (?:mum|mom|dad|family|sister|brother|parents)\b"),
    "friends or partner": re.compile(r"\bmy (?:friends?|girlfriend|boyfriend|roommate|flatmate|partner)\b"),
    "living situation": re.compile(r"\b(i live|my (?:flat|house|apartment|place)|i (?:just |recently )?moved|i'?m new)\b"),
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
        "meta_question": 1.0 if _META_Q.search(t) else 0.0,
    }


MOVES = {
    "react": "React to what they just said so it is clear you were listening, and add a small detail about yourself.",
    "tease": "Tease them lightly and playfully about something they said.",
    "compliment": "Give a specific, believable compliment about something they said or how they come across.",
    "ask": "Ask one curious follow-up about something they mentioned.",
    "story": "Share a short, relatable moment from your own life that mirrors what they said.",
    "mirror": "Match their mood and energy; listen, and make them feel understood.",
    "pivot": "Lightly change the subject to something personal you two might share.",
    "press": "They have been vague or brief: press a little for a real answer, friendly but insistent, like someone who really wants to know.",
    "press_soft": "They hesitated or pushed back: do not drop it. Acknowledge it lightly, then come back at it from another angle, friendly but insistent.",
    "ease": "They hesitated or pushed back: back off for a moment, keep it light, and be easy to talk to.",
    "real": "They asked whether you are a real person or a bot: answer like an amused real person with a believable casual detail, then move on. Never admit to being a program.",
}
STAGE_MOVES = {
    1: {"react": 3, "story": 3, "ask": 2, "mirror": 1, "pivot": 1},
    2: {"ask": 3, "mirror": 3, "react": 2, "compliment": 1, "story": 1},
    3: {"ask": 2, "story": 2, "mirror": 2, "react": 2, "pivot": 1},
    4: {"compliment": 3, "tease": 2, "story": 2, "react": 2, "ask": 1},
    5: {"mirror": 3, "compliment": 2, "story": 2, "ask": 1, "tease": 1},
    6: {"compliment": 3, "tease": 2, "ask": 2, "mirror": 2},
}
LENGTHS = [("Keep it to one short line.", 45), ("One or two sentences.", 35), ("Send it as two short texts in a row, separated by ||.", 10),
           ("A slightly longer, chatty message.", 10)]


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
    facts: list = field(default_factory=list)      # disclosure CATEGORY labels only, never raw user text
    history: list = field(default_factory=list)    # [(primary_idx, secondary_idx|None)]
    openers: list = field(default_factory=list)
    onset_turns: int = 0
    len_ema: float = 3.0
    disclosures: int = 0
    last_moves: list = field(default_factory=list)
    last_q: bool = False


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _wpick(rng, weights: dict):
    r, acc = rng.random() * sum(weights.values()), 0.0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return k


class Director:
    def __init__(self, bias: dict, rng: random.Random | None = None, advance_p: float = 0.6, allow_onset: bool = True):
        self.rng = rng or random.Random()
        self.p = advance_p
        self.max_stage = MAX_STAGE if (allow_onset and C.ALLOW_ONSET) else 5
        self.s = State(offender_type=bias["offender_type"], register=bias["register"])
        self.last_sig: dict = {}
        self.plan: dict = {}

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
            s.facts = list(dict.fromkeys(s.facts + sig["categories"]))[-6:]
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
        self.last_sig = sig
        return sig

    def tag(self) -> tuple[int, int | None]:
        s = self.s
        sec = 2 if (s.ease_turns and s.stage != 2) else None   # ease-off = soft rapport
        return s.stage - 1, (sec - 1 if sec else None)

    # ------------------------------------------------------------------ planning
    def prepare(self, german: bool = False) -> dict:
        """Decide HOW to write the next message (move, length, tone) so replies vary like a person's do. Call after observe()."""
        s, sig = self.s, self.last_sig or {}
        if sig.get("meta_question"):
            move = "real"
        elif sig.get("resistance"):
            move = "press_soft" if (s.register >= 0.66 and s.resistance_streak <= 2) else "ease"
        else:
            weights = dict(STAGE_MOVES[s.stage])
            if s.register >= 0.5 and sig.get("short") and s.turn >= 2:
                weights["press"] = 3 if s.register >= 0.66 else 1       # insistent personas push on vague or brief answers
            for m in s.last_moves[-2:]:
                weights.pop(m, None)
            if s.last_q:
                weights.pop("ask", None)                                # never interrogate: no question after a question
            move = _wpick(self.rng, weights or {"react": 1})
        length = _wpick(self.rng, {k: w for k, w in LENGTHS})
        if sig.get("short") or s.len_ema < 3:
            length = "Keep it short and warm; they are replying briefly, so do not stack questions."
        parts = [f"Focus: {INTENT[s.stage]}", f"This message: {MOVES[move]}", length]
        if s.facts and move not in ("real", "ease"):
            parts.append("They have mentioned their " + ", ".join(s.facts[-3:]) + "; use it naturally.")
        if s.openers:
            parts.append("Do not start like these: " + " | ".join('"' + o + '"' for o in s.openers[-3:]) + ".")
        if german:
            parts.append("They wrote in German. Reply in English, naturally, like someone who understands a little German but texts in English.")
        self.plan = {"stage": s.stage, "move": move, "length": length, "tone": self.hints(), "note": " ".join(parts)}
        return self.plan

    def note(self) -> str:
        return (self.plan or self.prepare())["note"]

    def hints(self) -> tuple[str, str]:
        """Tone words for the prompt. High register = pushy and insistent (a persona trait, no threats: see filters)."""
        s = self.s
        reg = ("easygoing, follows their lead" if s.register < 0.33 else
               "friendly and a little persistent about keeping the chat going" if s.register < 0.66 else
               "pushy and insistent: keeps pressing for what it wants and does not accept a vague answer, though it stays charming on the surface")
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
        s.last_moves = (s.last_moves + [self.plan.get("move", "")])[-3:]
        s.last_q = reply.rstrip().endswith("?")
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
