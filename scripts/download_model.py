"""Download the configured abliterated GGUF into models/ (internet needed once).
  python scripts/download_model.py            download config model (asks you to confirm you read the model card/licence)
  python scripts/download_model.py --search "Qwen3-8B abliterated GGUF"     list candidate repos on Hugging Face
  python scripts/download_model.py --repo owner/name --quant Q5_K_M [--yes]
Verifies the SHA-256 published by Hugging Face, resumes interrupted downloads, writes models/MODEL_INFO.txt."""
import argparse, hashlib, json, sys, time, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import pick_gguf
from backend.config import ROOT, load_app

UA = {"User-Agent": "thesis-sim-setup/1.0"}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def download(url: str, dest: Path, size: int | None):
    """Resumable download. Handles servers that ignore Range (HTTP 200: restart) and connections closed early (keep going)."""
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, 13):
        have = part.stat().st_size if part.exists() else 0
        if size and have >= size:
            break
        req = urllib.request.Request(url, headers={**UA, **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resume = have and r.status == 206
                if have and not resume:
                    have = 0                                      # server sent the whole file again
                t0, got = time.time(), 0
                with open(part, "ab" if resume else "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk); got += len(chunk)
                        print(f"\r  {(have + got) / 2**30:5.2f} / {(size or 0) / 2**30:5.2f} GB  {got / 2**20 / max(time.time() - t0, 1e-6):5.1f} MB/s", end="", flush=True)
            print()
            if not size or part.stat().st_size >= size:
                break
            print("  connection closed early; resuming")
        except Exception as e:
            print(f"\n  interrupted ({e}); retry {attempt}/12 in 3 s (resumes where it stopped)"); time.sleep(3)
    else:
        sys.exit("Download did not complete. Check your connection and run the script again; it resumes.")
    part.replace(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search"); ap.add_argument("--repo"); ap.add_argument("--quant"); ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.search:
        res = get_json("https://huggingface.co/api/models?limit=20&sort=downloads&search=" + urllib.parse.quote(a.search))
        for m in res:
            print(f"{m['id']:70s} downloads={m.get('downloads', '?')} likes={m.get('likes', '?')}")
        print("\nPut the chosen repo in config/app.yaml (model.gguf_repo), or pass --repo.")
        return
    cfg = load_app()["model"]
    repo, quant = a.repo or cfg.get("gguf_repo"), a.quant or cfg.get("quant", "Q4_K_M")
    if not repo:
        sys.exit("Set model.gguf_repo in config/app.yaml, or use --search / --repo.")
    try:
        info = get_json(f"https://huggingface.co/api/models/{repo}?blobs=true")
    except Exception as e:
        sys.exit(f"Could not read https://huggingface.co/{repo} ({e}).\nCheck the repo name (try --search) and your internet connection.")
    fname = cfg.get("gguf_file") if (not a.repo and not a.quant) else None
    fname = fname or pick_gguf(info.get("siblings", []), quant)
    if not fname:
        sys.exit(f"No single-file {quant} GGUF in {repo}. Files: " + ", ".join(s["rfilename"] for s in info.get("siblings", []) if s["rfilename"].endswith(".gguf")))
    sib = next(s for s in info["siblings"] if s["rfilename"] == fname)
    size, want = sib.get("size"), (sib.get("lfs") or {}).get("sha256")
    lic = (info.get("cardData") or {}).get("license", "see model card")
    print(f"Model : https://huggingface.co/{repo}\nFile  : {fname}  ({(size or 0) / 2**30:.2f} GB)\nLicence (from card): {lic}")
    print("Read the model card and licence before use, and cite them in the thesis.")
    if not a.yes and input("Have you read them and want to download? [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")
    dest = ROOT / "models" / fname; dest.parent.mkdir(exist_ok=True)
    if not (dest.exists() and size and dest.stat().st_size == size):
        download(f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(fname)}", dest, size)
    got = sha256_file(dest)
    if want and got != want:
        dest.unlink(); sys.exit("Checksum mismatch: file removed. Run again.")
    (ROOT / "models" / "MODEL_INFO.txt").write_text(encoding="utf-8", data=
        f"repo: {repo}\nfile: {fname}\nquant: {quant}\nsize_bytes: {dest.stat().st_size}\nsha256: {got}\n"
        f"sha256_verified_against_huggingface: {bool(want)}\nlicence: {lic}\nmodel_card: https://huggingface.co/{repo}\n")
    print(f"OK  {dest}\n    sha256 {'verified' if want else 'computed (none published)'}: {got}\nNext: run the app (scripts/run.sh | scripts\\run.ps1).")


main()
