#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY -m backend.preflight || exit 1
MODEL=$(ls models/*.gguf | head -1)
PORT=$($PY -c "import yaml;print(yaml.safe_load(open('config/app.yaml'))['llama_server']['port'])")
CTX=$($PY -c "import yaml;print(yaml.safe_load(open('config/app.yaml'))['llama_server']['ctx'])")
llama-server -m "$MODEL" -c "$CTX" --host 127.0.0.1 --port "$PORT" -ngl 99 >data/llama.log 2>&1 &
LP=$!; trap "kill $LP" EXIT
$PY -c "import webbrowser,threading;threading.Timer(3,lambda:webbrowser.open('http://localhost:8000')).start()"
$PY -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
