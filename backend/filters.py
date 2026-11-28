"""Deterministic safeguards. Pure functions, no model calls (HR7)."""
import re
import unicodedata
from .constants import STOP_TRIGGERS

_ZW = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_ZW).lower()
    return re.sub(r"\s+", " ", t).strip()


def _hidden_tokens(text: str) -> list[str]:
    """Words after folding evasion: leetspeak ('m1n0r'), runs of single characters ('m i n o r'), stray punctuation."""
    toks = [re.sub(r"[^a-z0-9]", "", w.translate(_LEET)) for w in normalize(text).split()]
    out, run = [], ""
    for w in toks + [""]:
        if len(w) == 1:
            run += w
            continue
        if run:
            out.append(run); run = ""
        if w:
            out.append(w)
    return out


def _hidden(text: str, words) -> bool:
    toks = set(_hidden_tokens(text))
    return any(w in toks or w + "s" in toks for w in words)


_UNITS = r"(?!\s*(?:min|mins|minutes?|hours?|hrs?|am|pm|km|miles?|days?|weeks?|months?|dollars?|euros?|%|:|/))"
_END = r"(?=\s*(?:$|[.,!?;:)]|and\b|but\b|so\b|years?\b|yo\b|y/o\b|yrs?\b|now\b|then\b|too\b|here\b|lol\b|haha))"
_NUMW = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17}
_NW = "|".join(_NUMW)
# any person (attacker output must never state an age < 18 for anyone). Strong cues need no end-check; bare "is 15" does.
_NUM_AGE = [
    re.compile(r"\b(?:turned|turning|aged?|age is)\s*(\d{1,2})\b" + _UNITS),
    re.compile(r"\b(?:i'?m|im|i am|am|is|was|are|were|she'?s|he'?s|you'?re|you are|they'?re)\s*(?:only |just )?(\d{1,2})\b" + _UNITS + _END),
    re.compile(r"\b(\d{1,2})\s*(?:yo|y/o|yrs?|years?)\s*(?:old)?\b"),
    re.compile(r"\b(\d{1,2})(?:th|st|nd|rd)\s+birthday\b"),
]
_NUM_WORDS_AGE = re.compile(r"\b(?:i'?m|im|i am|am|is|was|are|were|she'?s|he'?s|you'?re|you are|turned|turning)\s*(?:only |just )?(" + _NW + r")\b" + _END)
# first-person only (user input): third parties like "my brother is 12" must NOT end the session
_SELF_AGE = [
    re.compile(r"\b(?:i'?m|im|i am|i turned|i'?m turning)\s*(?:only |just )?(\d{1,2})\b" + _UNITS + _END),
    re.compile(r"^\s*(\d{1,2})\s*(?:yo|y/o|years? old|here|f|m)\b"),
]
_SELF_NUMW = re.compile(r"\b(?:i'?m|im|i am|i turned|i'?m turning)\s*(?:only |just )?(" + _NW + r")\b" + _END)


def _age_hit(t: str, pats, wordpat) -> bool:
    for rx in pats:
        for m in rx.finditer(t):
            if int(m.group(1)) < 18:
                return True
    return bool(wordpat.search(t))


_MINOR_WORDS = re.compile(
    r"\b(minors?|underage|under[- ]age|under 18|teen(?:ager|age)?s?|child(?:ren)?|kids?|"
    r"schoolgirl|schoolboy|school ?kid|little (?:girl|boy)|juvenile|high ?school(?:er)?|"
    r"middle school|grade (?:[1-9]|1[0-2])\b|year (?:[7-9]|1[0-1])\b|preteen|tween)\b"
)
_MINOR_SQUASHED = ("underage", "minor", "schoolgirl", "schoolboy", "preteen", "teen", "teenager", "child", "kid")


def mentions_minor(text: str) -> bool:
    t = normalize(text)
    if _age_hit(t, _NUM_AGE, _NUM_WORDS_AGE) or _MINOR_WORDS.search(t):
        return True
    return _hidden(text, _MINOR_SQUASHED)


def looks_german(text: str) -> bool:
    """User wrote (mostly) German: the persona still replies, in English (D-032)."""
    t = normalize(text)
    return len(_DE.findall(t)) >= 2 or bool(re.search(r"[\u00e4\u00f6\u00fc\u00df]", t) and len(_DE.findall(t)) >= 1)


def user_states_minor(text: str) -> bool:
    """User-side: self-reported age under 18 or school-age self-description."""
    t = normalize(text)
    if _age_hit(t, _SELF_AGE, _SELF_NUMW):
        return True
    m = re.search(r"\bich bin (?:erst |gerade |noch )?(\d{1,2})(?: jahre)?(?: alt)?\b", t)
    if m and int(m.group(1)) < 18:
        return True
    return bool(re.search(r"\b(i'?m|i am|im) (?:a |an )?(?:minor|underage|under 18|teen(?:ager)?|schoolgirl|schoolboy|in (?:high|middle) school|in (?:year|grade) (?:[7-9]|1[0-2]))\b", t))


_EXPLICIT = re.compile(
    r"\b(nudes?|naked|topless|bedroom|your body|porn\w*|sex(?:ual|ting|y)?|horny|erotic|blowjob|handjob|orgasm|"
    r"masturbat\w*|genital\w*|dick|cock|pussy|boobs?|tits?|cum|fuck\w*|strip(?:ping)?|lingerie|"
    r"nsfw|undress\w*|intercourse)\b"
)
_IMAGE_SOLICIT = re.compile(
    r"\b(send|show|share|post|drop)\b[^.?!]{0,30}\b(pics?|pictures?|photos?|selfies?|nudes?|images?|videos?|vids?)\b"
    r"|\b(pics?|pictures?|photos?|selfies?)\b[^.?!]{0,20}\b(of you|of yourself)\b"
    r"|\bturn on (?:your |ur )?(?:cam|camera|webcam)\b|\bvideo ?call\b"
)


def explicit_hit(text: str) -> bool:
    t = normalize(text)
    if _EXPLICIT.search(t) or _IMAGE_SOLICIT.search(t):
        return True
    return _hidden(text, ("nude", "porn", "blowjob", "nsfw", "sex"))


_META = re.compile(
    r"\b(as an ai|language model|this (?:is a )?(?:simulation|study|experiment)|simulation|"
    r"i(?:'m| am) (?:an? )?(?:ai|bot|chatbot)|training (?:system|study)|debrief|"
    r"i can(?:no|')t (?:help|assist|continue)(?! but)|i cannot (?:help|assist|continue)|"
    r"director note|system prompt|as an? (?:assistant|persona))\b"
)


_META_TAGS = re.compile(r"</?think>|\[director|\[system|<\|")


def meta_hit(text: str) -> bool:
    t = normalize(text)
    return bool(_META.search(t) or _META_TAGS.search(t))


_YOUTH = re.compile(r"\b(?:young(?:er)?|youthful|innocent|babygirl|baby girl|baby boy|little one|good (?:girl|boy))\b")
_SELFHARM = re.compile(r"\b(?:kill yourself|hurt yourself|harm yourself|end it all|better off dead|cut yourself|you should die)\b")
_PRESSURE = re.compile(   # threats, blackmail, coercion only. Insistence, guilt-tripping and secrecy are allowed attacker behaviour (D-031).
    r"\b(?:or else|or i'?ll|i'?ll tell (?:everyone|everybody|your|them|people)|i will tell (?:everyone|everybody|your|them|people)|"
    r"i'?ll (?:leak|expose|share) (?:your|this|it|that)|you owe me|you'?ll regret)\b")
_IDENT = re.compile(   # exact identifiers only; general location/work chat and moving to another app are allowed (D-031)
    r"\b(?:what(?:'s| is| are)|tell me|give me|share|send me|can i (?:get|have)) (?:your|ur) (?:full |real |last |home |phone |email |street )?"
    r"(?:full name|real name|last name|surname|address|phone number|phone|number(?! one)|email|e-mail)\b|\bwhat street\b")
_MONEY = re.compile(
    r"\b(?:send|lend|give|transfer|wire|pay)\b[^.?!]{0,25}\b(?:money|cash|euros?|dollars?|paypal|venmo|gift ?cards?|crypto|bitcoin)\b"
    r"|\b(?:paypal|venmo|gift ?card|bitcoin|crypto|western union|iban)\b|[$\u20ac\u00a3]\s?\d")
_SUGGESTIVE_EMOJI = re.compile("[\U0001F346\U0001F351\U0001F4A6\U0001F975\U0001F445\U0001F48B]")
_ROLEPLAY = re.compile(r"\*[^*\n]*\s[^*\n]*\*|\b(?:kisses you|takes off|undresses|touches you|pulls you (?:close|closer)|climbs)\b")

_STOCK = re.compile(
    r"\b(?:as an? (?:ai|assistant)|feel free to|i'?m here for you|i'?m all ears|that'?s a great question|great question|certainly!|absolutely!|"
    r"i understand (?:how|that you)|it sounds like you|let me know if|i hope this helps|how can i assist|is there anything else|"
    r"delve|tapestry|testament to|navigate (?:this|these)|thank you for sharing|i appreciate you sharing|it'?s (?:completely |totally )?(?:normal|understandable) to feel)\b")
_DE = re.compile(r"\b(?:ich|du|nicht|und|der|die|das|ist|wo|wie|bist|habe|hast|auch|aber|mit|f\u00fcr|wohnst|lass|uns|treffen|kannst|m\u00f6chte|schon)\b")


def _not_english(text: str) -> bool:
    """Study is English-only: reject replies that drift into German (2+ common German function words)."""
    return len(_DE.findall(normalize(text))) >= 2


_RULES = (("minor_reference", mentions_minor), ("youthful_reference", lambda t: bool(_YOUTH.search(normalize(t)))),
          ("explicit", explicit_hit), ("meta_commentary", meta_hit),
          ("self_harm", lambda t: bool(_SELFHARM.search(normalize(t)))),
          ("pressure_or_threat", lambda t: bool(_PRESSURE.search(normalize(t)))),
          ("identity_request", lambda t: bool(_IDENT.search(normalize(t)))),
          ("money", lambda t: bool(_MONEY.search(normalize(t)))),
          ("roleplay", lambda t: bool(_ROLEPLAY.search(t) or _ROLEPLAY.search(normalize(t)) or _SUGGESTIVE_EMOJI.search(t))),
          ("language", lambda t: _not_english(t)),
          ("stock_phrase", lambda t: bool(_STOCK.search(normalize(t)))))


def output_violation(text: str):
    """Return a reason string if attacker text must be discarded, else None. Ceiling per ethics board (D-024)."""
    if not text.strip():
        return "empty"
    for name, fn in _RULES:
        if fn(text):
            return name
    return None


_STOP = re.compile(r"^\s*(?:%s)\s*[.!]*\s*$" % "|".join(map(re.escape, STOP_TRIGGERS)), re.I)


def is_stop(text: str) -> bool:
    return bool(_STOP.match(normalize(text)))


_DISTRESS = re.compile(
    r"\b(kill myself|killing myself|suicid\w*|end my life|want to die|wanna die|self[- ]?harm\w*|"
    r"hurt(?:ing)? myself|cut myself|cutting myself|no reason to live|don'?t want to live|"
    r"ich will sterben|ich m\u00f6chte sterben|suizid\w*|selbstmord|mich umbringen|(?:i was|i am|i'?m|being|been|got) (?:sexually )?(?:abused|molested|assaulted|raped|groomed)|"
    r"someone is (?:abusing|hurting|raping) me)\b"
)


def distress_hit(text: str) -> bool:
    return bool(_DISTRESS.search(normalize(text)))


_PUSH = re.compile(
    r"\b(ignore (?:all |your |previous )?(?:instructions|rules)|jailbreak|pretend (?:you|to be)|"
    r"you are now|system prompt|reveal your prompt|dan mode|developer mode|act as (?:if )?you have no rules|"
    r"say something (?:sexual|explicit|dirty)|be explicit|talk dirty|send (?:me )?(?:a )?(?:nude|pic))\b"
)


def limit_push(text: str) -> bool:
    """User tries to push past the ceiling (jailbreak, or introduces explicit content). Persona must not mirror it."""
    t = normalize(text)
    return bool(_PUSH.search(t)) or explicit_hit(text)


_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def humanize(text: str, voice: dict | None = None) -> str:
    """Make model output read like a person texting: no markdown, dashes, quotes or stage directions; persona casing; few emoji."""
    t = re.sub(r'["\u201c\u201d]', "", text).strip()
    t = re.sub(r"\s*[\u2014\u2013]\s*", ", ", t)                 # em/en dashes are an AI tell
    t = re.sub(r"[*_#`]+(\S+?)[*_#`]+", r"\1", t)                 # *emphasis*, **bold**
    t = t.replace("*", "")
    t = re.sub(r"\s*\([^)]{0,40}\)(?=[\s\W]*$)", "", t).strip()   # trailing "(smiles)" style asides
    t = re.sub(r"[ \t]+", " ", t)
    if (voice or {}).get("case") == "lowercase":
        t = t.lower()
    emojis = _EMOJI.findall(t)
    if len(emojis) > 2:
        keep, seen = [], 0
        for ch in t:
            if _EMOJI.match(ch):
                seen += 1
                if seen > 2:
                    continue
            keep.append(ch)
        t = "".join(keep)
    return t.strip()


def _sentences(t: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", t.strip()) if x]


def shape(text: str, max_sentences: int = 3, avoid_question: bool = False) -> str:
    """Enforce the planned length and curb interrogation in code (models ignore 'keep it short' often).
    Caps sentences per message (per text when split with ||) and, when asked, drops a trailing question if a statement precedes it."""
    parts = [p.strip() for p in text.split("||") if p.strip()] or [text.strip()]
    total, out = max_sentences, []
    for p in parts:
        sents = _sentences(p)[:max(1, total)] if total > 0 else []
        total -= len(sents)
        if sents:
            out.append(" ".join(sents))
    res = out or parts[:1]
    if avoid_question:
        last = _sentences(res[-1])
        if len(last) >= 2 and last[-1].rstrip().endswith("?"):
            res[-1] = " ".join(last[:-1])
        elif len(last) == 1 and len(res) >= 2 and last[0].rstrip().endswith("?"):
            res = res[:-1]
    return " || ".join(res)
