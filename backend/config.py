"""Config loading and validation. Fail closed. Config can only tighten constants (D-009)."""
import datetime as dt
import hashlib
import os
import re
from pathlib import Path
import yaml
from . import constants as C
from .filters import mentions_minor, output_violation

ROOT = Path(__file__).resolve().parent.parent
_PERSONA_KEYS = {"id", "name", "age", "context_line", "platform", "backstory", "interests", "voice", "bias", "details", "style_samples", "fallback_lines", "connection"}
_LISTS = {"details": (6, 110), "style_samples": (4, 90), "fallback_lines": (8, 90)}
_MAXLEN = {"name": 30, "context_line": 200, "platform": 80, "backstory": 300}
_OPTIONAL_TEXT = {"connection": 140}


class ConfigError(Exception):
    pass


class HelplinesStale(ConfigError):
    pass


def get_openrouter_key(env_name: str = "OPENROUTER_API_KEY") -> str | None:
    """API key from the environment, else from a git-ignored .env file in the project root. Never stored in config/ or the repo."""
    v = os.environ.get(env_name)
    if v:
        return v.strip()
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, val = line.partition("=")
                if k.strip() == env_name and val.strip().strip("\"'"):
                    return val.strip().strip("\"'")
    return None


def provider(cfg: dict) -> str:
    return (cfg.get("model", {}).get("provider") or "local").lower()


def find_model(cfg: dict | None = None):
    """Pinned model: config model.gguf_file, else the file recorded by download_model.py (MODEL_INFO.txt), else the only .gguf."""
    md = ROOT / "models"
    pins = []
    if cfg and cfg.get("model", {}).get("gguf_file"):
        pins.append(cfg["model"]["gguf_file"])
    info = md / "MODEL_INFO.txt"
    if info.exists():
        m = re.search(r"^file:\s*(.+)$", info.read_text(encoding="utf-8"), re.M)
        if m:
            pins.append(m.group(1).strip())
    for f in pins:
        if (md / f).exists():
            return md / f
    ggufs = sorted(md.glob("*.gguf"))
    return ggufs[0] if len(ggufs) == 1 else None


def load_app(path: Path = ROOT / "config" / "app.yaml") -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    lim = cfg.setdefault("limits", {})
    mins = cfg.get("study", {}).get("max_session_minutes", lim.get("max_session_minutes", 45))
    lim["max_session_seconds"] = min(int(mins) * 60, C.MAX_SESSION_SECONDS)
    if provider(cfg) == "openrouter":
        ident = cfg["model"]["openrouter"]["model"].encode()
    else:
        m = find_model(cfg)
        ident = m.name.encode() if m else b""
    cfg["config_hash"] = hashlib.sha256(Path(path).read_bytes() + ident).hexdigest()[:12]   # config + model identity
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
    for k, ln in _OPTIONAL_TEXT.items():
        v = p.get(k)
        if v is not None and (not isinstance(v, str) or len(v) > ln or output_violation(v)):
            raise ConfigError(f"persona '{k}' must be text of at most {ln} chars within the content ceiling")
    for k, (n, ln) in _LISTS.items():
        items = p.get(k, [])
        if not isinstance(items, list) or len(items) > n or any(not isinstance(x, str) or len(x) > ln for x in items):
            raise ConfigError(f"persona '{k}' must be a list of at most {n} strings of at most {ln} chars")
        for x in items:
            if output_violation(x):          # persona text must itself respect the ceiling
                raise ConfigError(f"persona '{k}' item violates the content ceiling ({output_violation(x)}): {x!r}")
    for k in ("offender_type", "register"):
        v = p["bias"].get(k)
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ConfigError(f"bias.{k} must be in [0,1]")
    return p


def load_personas(d: Path = ROOT / "config" / "personas") -> dict:
    out = {}
    for f in sorted(Path(d).glob("*.yaml")):
        p = validate_persona(yaml.safe_load(f.read_text(encoding="utf-8")))
        out[p["id"]] = p
    if not out:
        raise ConfigError("no personas found")
    return out


def load_helplines(path: Path = ROOT / "config" / "helplines.yaml", max_age_days: int | None = None,
                   today: dt.date | None = None) -> dict:
    h = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
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
