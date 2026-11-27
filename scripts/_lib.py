"""Pure helpers shared by the setup scripts (unit-tested without network)."""
import re


def pick_gguf(siblings: list[dict], quant: str) -> str | None:
    """Choose a single-file GGUF for the quant, e.g. 'Q4_K_M'. Skips split files and imatrix files."""
    q = quant.lower()
    cands = [s["rfilename"] for s in siblings if s["rfilename"].lower().endswith(".gguf")
             and re.search(r"(?<![a-z0-9])" + re.escape(q) + r"(?![a-z0-9])", s["rfilename"].lower().replace("-", "_").replace(".", "_"))
             and "-of-" not in s["rfilename"] and "imatrix" not in s["rfilename"].lower()]
    return sorted(cands, key=len)[0] if cands else None


def pick_llama_asset(names: list[str], system: str, machine: str) -> str | None:
    """Pick the official llama.cpp release asset (Vulkan on Windows/Linux, Metal-capable arm64 build on macOS)."""
    n = [x for x in names if x.endswith((".zip", ".tar.gz")) and "cudart" not in x and "xcframework" not in x]
    system, arm = system.lower(), machine.lower() in ("arm64", "aarch64")
    if system == "windows":
        want = ["win", "vulkan", "x64"]
    elif system == "darwin":
        want = ["macos", "arm64" if arm else "x64"]
    else:
        want = ["ubuntu", "vulkan", "arm64" if arm else "x64"]
    hits = [x for x in n if all(w in x.lower() for w in want)]
    return sorted(hits, key=len)[0] if hits else None
