"""One-command start: preflight -> llama-server -> wait until ready -> participant app -> browser. Ctrl+C stops everything.
Options: --cpu (no GPU offload, use if Vulkan fails)  --port 8000  --no-browser"""
import argparse, subprocess, sys, threading, time, urllib.request, webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import ROOT, load_app
from backend.config import find_model, provider
from backend.preflight import check, find_llama_server

ap = argparse.ArgumentParser(); ap.add_argument("--cpu", action="store_true"); ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--no-browser", action="store_true"); a = ap.parse_args()
errs = check()
if errs:
    print("\nCannot start yet:\n" + "\n".join("  - " + e for e in errs)); sys.exit(1)
cfg = load_app(); ls = cfg["llama_server"]; (ROOT / "data").mkdir(exist_ok=True)
import socket
remote = provider(cfg) != "local"
for port in ([a.port] if remote else [ls["port"], a.port]):
    with socket.socket() as sk:
        if sk.connect_ex(("127.0.0.1", port)) == 0:
            print(f"\nPort {port} is already in use (an old server still running?). Close it or choose another port in config/app.yaml / --port."); sys.exit(1)
proc = None
if remote:
    sec = cfg["model"][provider(cfg)]
    print(f"Model: {sec['model']} via {sec.get('display_name', provider(cfg))} (messages are sent to an external service).")
else:
    cmd = [find_llama_server(ls["binary"]), "-m", str(find_model(cfg)), "-c", str(ls["ctx"]), "--host", ls["host"], "--port", str(ls["port"]),
           "-ngl", "0" if a.cpu else str(ls.get("gpu_layers", 99)), "--jinja", *map(str, ls.get("extra_args", []))]
    log = open(ROOT / "data" / "llama.log", "w", encoding="utf-8")
    print("Starting model server (loading a ~5 GB model; first start can take a minute)...")
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
try:
    t0 = time.time()
    while proc is not None:
        if proc.poll() is not None:
            tail = (ROOT / "data" / "llama.log").read_text(encoding="utf-8", errors="ignore").splitlines()[-15:]
            print("\nModel server exited:\n  " + "\n  ".join(tail) + "\n\nIf this is a GPU/Vulkan problem, try: scripts/run.sh --cpu"); sys.exit(1)
        try:
            if urllib.request.urlopen(f"http://{ls['host']}:{ls['port']}/health", timeout=2).status == 200:
                break
        except Exception:
            pass
        if time.time() - t0 > 300:
            print("Model server did not become ready within 5 minutes. See data/llama.log"); sys.exit(1)
        time.sleep(1.5)
    print(f"Ready in {time.time() - t0:.0f}s. Participant app: http://localhost:{a.port}   (Ctrl+C to stop)")
    print("Researcher log viewer (separate terminal): scripts/researcher.sh | scripts\\researcher.ps1")
    if not a.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{a.port}")).start()
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=a.port, log_level="warning")
finally:
    if proc is not None:
        proc.terminate()
