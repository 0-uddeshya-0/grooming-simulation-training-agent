"""Download the official llama.cpp release (Vulkan build on Windows/Linux) into bin/llama/ (internet needed once).
If this fails, download a release manually from https://github.com/ggml-org/llama.cpp/releases and put llama-server on PATH."""
import json, platform, stat, sys, tarfile, urllib.request, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import pick_llama_asset
from backend.config import ROOT, load_app, provider
from backend.preflight import find_llama_server

UA = {"User-Agent": "thesis-sim-setup/1.0"}
if provider(load_app()) != "local":
    print("Model provider is a cloud service: no local llama.cpp needed."); sys.exit(0)
if find_llama_server():
    print("llama-server already available:", find_llama_server()); sys.exit(0)
try:
    rel = json.load(urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest", headers=UA), timeout=60))
    assets = {a["name"]: a["browser_download_url"] for a in rel["assets"]}
    name = pick_llama_asset(list(assets), platform.system(), platform.machine())
    if not name:
        sys.exit("No matching build found. Assets: " + ", ".join(assets) + "\nDownload one manually and put llama-server on PATH.")
    dest = ROOT / "bin" / name; dest.parent.mkdir(exist_ok=True)
    print("Downloading", name, "(release", rel["tag_name"] + ")")
    urllib.request.urlretrieve(assets[name], dest)
    out = ROOT / "bin" / "llama"; out.mkdir(exist_ok=True)
    if name.endswith(".zip"):
        zipfile.ZipFile(dest).extractall(out)
    else:
        tarfile.open(dest).extractall(out)
    dest.unlink()
    (out / "LLAMA_INFO.txt").write_text(encoding="utf-8", data=f"llama.cpp release {rel['tag_name']}\nasset {name}\nlicence: MIT (ggml-org/llama.cpp)\n")
    exe = find_llama_server()
    if exe and platform.system() != "Windows":
        Path(exe).chmod(Path(exe).stat().st_mode | stat.S_IEXEC)
    print("OK:", exe or "extracted, but llama-server not found inside; check bin/llama/")
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Could not download llama.cpp automatically ({e}).\nDownload a release manually from https://github.com/ggml-org/llama.cpp/releases and put llama-server on PATH.")
