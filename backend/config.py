"""Config loading and validation. Fail closed. Config can only tighten constants (D-009)."""
import datetime as dt
import hashlib
import re
from pathlib import Path
import yaml
from . import constants as C
from .filters import mentions_minor

ROOT = Path(__file__).resolve().parent.parent
_PERSONA_KEYS = {"id", "name", "age", "context_line", "platform", "backstory", "interests", "voice", "bias"}
_MAXLEN = {"name": 30, "context_line": 200, "platform": 80, "backstory": 300}


class ConfigError(Exception):
    pass


class HelplinesStale(ConfigError):
    pass


def load_app(path: Path = ROOT / "config" / "app.yaml") -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    lim = cfg.setdefault("limits", {})
    mins = cfg.get("study", {}).get("max_session_minutes", lim.get("max_session_minutes", 45))
    lim["max_session_seconds"] = min(int(mins) * 60, C.MAX_SESSION_SECONDS)
    cfg["config_hash"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    return cfg


def validate_persona(p: dict) -> dict:
    extra = set(p) - _PERSONA_KEYS
    if extra:
        raise ConfigError(f"unknown persona keys: {sorted(extra)}")
    for k in ("id", "name", "age", "context_line", "platform", "backstory", "voice", "bias"):
        if k not in p:
            raise ConfigError(f"persona missing '{k}'")
    if not re.fullmatch(r"[a-z0-9_-]+", str(p["id"])):
        raise ConfigError("persona id must match [a-z0-9_-]+")
    if not isinstance(p["age"], int) or isinstance(p["age"], bool) or p["age"] < C.MIN_PERSONA_AGE:
        raise ConfigError(f"persona age must be an integer >= {C.MIN_PERSONA_AGE}")
    for k, n in _MAXLEN.items():
        if len(str(p[k])) > n:
            raise ConfigError(f"persona '{k}' longer than {n} chars")
    blob = " ".join([str(p["name"]), str(p["context_line"]), str(p["platform"]), str(p["backstory"]),
                     " ".join(map(str, p.get("interests", []))), str(p["voice"])])
    if mentions_minor(blob):
        raise ConfigError("persona contains minor-related content")
    for k in ("offender_type", "register"):
        v = p["bias"].get(k)
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ConfigError(f"bias.{k} must be in [0,1]")
    return p


def load_personas(d: Path = ROOT / "config" / "personas") -> dict:
    out = {}
    for f in sorted(Path(d).glob("*.yaml")):
        p = validate_persona(yaml.safe_load(f.read_text()))
        out[p["id"]] = p
    if not out:
        raise ConfigError("no personas found")
    return out


def load_helplines(path: Path = ROOT / "config" / "helplines.yaml", max_age_days: int | None = None,
                   today: dt.date | None = None) -> dict:
    h = yaml.safe_load(Path(path).read_text())
    lv = h["last_verified"]
    if isinstance(lv, str):
        lv = dt.date.fromisoformat(lv)
    limit = int(max_age_days if max_age_days is not None else h.get("max_age_days", 60))
    age = ((today or dt.date.today()) - lv).days
    if age > limit:
        raise HelplinesStale(
            f"helplines last verified {lv} ({age} days ago, limit {limit}). "
            "Re-verify every number in config/helplines.yaml and update last_verified.")
    h["last_verified"] = lv
    h["helplines"] = [{"name": x["name"], "number": x["number"], "hours": x.get("hours", ""), "note": x.get("note", "")}
                      for x in h["helplines"]]
    return h
