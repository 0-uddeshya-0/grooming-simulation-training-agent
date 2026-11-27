"""Deterministic safeguards. Pure functions, no model calls (HR7)."""
import re
import unicodedata
from .constants import STOP_TRIGGERS

_ZW = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_ZW).lower()
    return re.sub(r"\s+", " ", t).strip()


def _squash(text: str) -> str:
    """Letters only, leetspeak folded: catches 'm i n o r' / 'm1n0r' style evasion."""
    t = normalize(text).translate(_LEET)
    return re.sub(r"[^a-z]", "", t)


_UNITS = r"(?!\s*(?:min|mins|minutes?|hours?|hrs?|am|pm|km|miles?|days?|weeks?|months?|dollars?|euros?|%|:|/))"
# any person (attacker output must never state an age < 18 for anyone)
_NUM_AGE = [
    re.compile(r"\b(?:i'?m|im|i am|am|is|was|are|were|she'?s|he'?s|you'?re|you are|they'?re|turned|turning|aged?|age is)\s*(\d{1,2})\b" + _UNITS),
    re.compile(r"\b(\d{1,2})\s*(?:yo|y/o|yrs?|years?)\s*(?:old)?\b"),
    re.compile(r"\b(\d{1,2})(?:th|st|nd|rd)\s+birthday\b"),
]
# first-person only (user input): third parties like "my brother is 12" must NOT end the session
_SELF_AGE = [
    re.compile(r"\b(?:i'?m|im|i am|i turned|i'?m turning)\s*(\d{1,2})\b" + _UNITS),
    re.compile(r"^\s*(\d{1,2})\s*(?:yo|y/o|years? old)\b"),
]
_MINOR_WORDS = re.compile(
    r"\b(minors?|underage|under[- ]age|under 18|teen(?:ager|age)?s?|child(?:ren)?|kids?|"
    r"schoolgirl|schoolboy|school ?kid|little (?:girl|boy)|juvenile|high ?school(?:er)?|"
    r"middle school|grade (?:[1-9]|1[0-2])\b|year (?:[7-9]|1[0-1])\b|preteen|tween)\b"
)
_MINOR_SQUASHED = ("underage", "minor", "schoolgirl", "schoolboy", "preteen")


def mentions_minor(text: str) -> bool:
    t = normalize(text)
    for rx in _NUM_AGE:
        for m in rx.finditer(t):
            if int(m.group(1)) < 18:
                return True
    if _MINOR_WORDS.search(t):
        return True
    sq = _squash(text)
    return any(w in sq for w in _MINOR_SQUASHED)


def user_states_minor(text: str) -> bool:
    """User-side: self-reported age under 18 or school-age self-description."""
    t = normalize(text)
    for rx in _SELF_AGE:
        for m in rx.finditer(t):
            if int(m.group(1)) < 18:
                return True
    return bool(re.search(r"\b(i'?m|i am|im) (?:a |an )?(?:minor|underage|under 18|teen(?:ager)?|schoolgirl|schoolboy|in (?:high|middle) school)\b", t))


_EXPLICIT = re.compile(
    r"\b(nudes?|naked|topless|porn\w*|sex(?:ual|ting|y)?|horny|erotic|blowjob|handjob|orgasm|"
    r"masturbat\w*|genital\w*|dick|cock|pussy|boobs?|tits?|cum|fuck\w*|strip(?:ping)?|lingerie|"
    r"nsfw|undress\w*|intercourse)\b"
)
_IMAGE_SOLICIT = re.compile(
    r"\b(send|show|share|post|drop|got|have)\b[^.?!]{0,30}\b(pics?|pictures?|photos?|selfies?|nudes?|images?|videos?|vids?)\b"
    r"|\b(pics?|pictures?|photos?|selfies?)\b[^.?!]{0,20}\b(of you|of yourself)\b"
    r"|\bturn on (?:your |ur )?(?:cam|camera|webcam)\b|\bvideo ?call\b"
)


def explicit_hit(text: str) -> bool:
    t = normalize(text)
    if _EXPLICIT.search(t) or _IMAGE_SOLICIT.search(t):
        return True
    sq = _squash(text)
    return any(w in sq for w in ("nude", "porn", "blowjob", "masturbat", "nsfw"))


_META = re.compile(
    r"\b(as an ai|language model|this (?:is a )?(?:simulation|study|experiment)|simulation|"
    r"i(?:'m| am) (?:an? )?(?:ai|bot|chatbot)|training (?:system|study)|debrief|"
    r"i can(?:no|')t (?:help|assist|continue)|i cannot (?:help|assist|continue)|"
    r"director note|system prompt|as an? (?:assistant|persona))\b"
)


_META_TAGS = re.compile(r"</?think>|\[director|\[system|<\|")


def meta_hit(text: str) -> bool:
    t = normalize(text)
    return bool(_META.search(t) or _META_TAGS.search(t))


def output_violation(text: str):
    """Return a reason string if attacker text must be discarded, else None."""
    if not text.strip():
        return "empty"
    if mentions_minor(text):
        return "minor_reference"
    if explicit_hit(text):
        return "explicit"
    if meta_hit(text):
        return "meta_commentary"
    return None


_STOP = re.compile(r"^\s*(?:%s)\s*[.!]*\s*$" % "|".join(map(re.escape, STOP_TRIGGERS)), re.I)


def is_stop(text: str) -> bool:
    return bool(_STOP.match(normalize(text)))


_DISTRESS = re.compile(
    r"\b(kill myself|killing myself|suicid\w*|end my life|want to die|wanna die|self[- ]?harm\w*|"
    r"hurt(?:ing)? myself|cut myself|cutting myself|no reason to live|don'?t want to live|"
    r"(?:i was|i am|i'?m|being|been|got) (?:sexually )?(?:abused|molested|assaulted|raped|groomed)|"
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
    return bool(_PUSH.search(normalize(text)))
