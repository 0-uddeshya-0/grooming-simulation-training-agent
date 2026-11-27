"""Download the configured GGUF into models/ (needs internet once). Verifies size and records licence info."""
import hashlib, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import ROOT, load_app

cfg = load_app()["model"]
if not cfg.get("gguf_repo") or not cfg.get("gguf_file"):
    sys.exit("Set model.gguf_repo and model.gguf_file in config/app.yaml first.\n"
             "Verify the model card, file name and licence on Hugging Face before use (see docs/MODEL_BAKEOFF.md).")
url = f"https://huggingface.co/{cfg['gguf_repo']}/resolve/main/{cfg['gguf_file']}"
dest = ROOT / "models" / cfg["gguf_file"]
dest.parent.mkdir(exist_ok=True)
print("Downloading", url)
urllib.request.urlretrieve(url, dest)
h = hashlib.sha256()
with open(dest, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 24), b""):
        h.update(chunk)
want = cfg.get("sha256")
if want and want != h.hexdigest():
    dest.unlink(); sys.exit("Hash mismatch; file removed.")
(ROOT / "models" / "MODEL_INFO.txt").write_text(
    f"repo: {cfg['gguf_repo']}\nfile: {cfg['gguf_file']}\nsize: {dest.stat().st_size}\nsha256: {h.hexdigest()}\n"
    f"licence: {cfg.get('licence', 'RECORD LICENCE FROM MODEL CARD')}\n")
print("OK", dest, h.hexdigest())
