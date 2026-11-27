"""Fail early with friendly messages (RAM, model, binary, helplines age)."""
import os
import shutil
import sys
from .config import ROOT, ConfigError, HelplinesStale, load_app, load_helplines, load_personas


def ram_gb() -> float:
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
        import ctypes
        class M(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("p", ctypes.c_ulong), ("tp", ctypes.c_ulonglong)] + [("x", ctypes.c_ulonglong)] * 5
        m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.tp / 2**30
    except Exception:
        return 0.0


def check(need_model=True) -> list[str]:
    errs = []
    try:
        cfg = load_app(); load_personas()
        load_helplines(max_age_days=cfg["limits"]["helplines_max_age_days"])
    except HelplinesStale as e:
        errs.append(f"HELPLINES: {e}")
    except ConfigError as e:
        errs.append(f"CONFIG: {e}")
        return errs
    r = ram_gb()
    if r and r < cfg["limits"]["min_free_ram_gb"] + 2:
        errs.append(f"RAM: {r:.1f} GB found; need at least {cfg['limits']['min_free_ram_gb'] + 2} GB.")
    if need_model:
        if not list((ROOT / "models").glob("*.gguf")):
            errs.append("MODEL: no .gguf in models/. Run: python scripts/download_model.py")
        if not shutil.which(cfg["llama_server"]["binary"]):
            errs.append("BINARY: llama-server not on PATH. Get llama.cpp releases (Vulkan build on Windows): "
                        "https://github.com/ggml-org/llama.cpp/releases")
    if "REPLACE" in cfg["study"]["researcher_contact"]:
        errs.append("CONFIG: set study.researcher_contact in config/app.yaml (shown in the debrief).")
    return errs


if __name__ == "__main__":
    errs = check(need_model="--no-model" not in sys.argv)
    for e in errs:
        print("ERROR:", e)
    sys.exit(1 if errs else 0)
