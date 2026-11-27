#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
mkdir -p data models
command -v llama-server >/dev/null || echo "NOTE: llama-server not found. Get llama.cpp from https://github.com/ggml-org/llama.cpp/releases and put it on PATH."
echo "Setup done. Next: .venv/bin/python scripts/download_model.py ; scripts/run.sh"
