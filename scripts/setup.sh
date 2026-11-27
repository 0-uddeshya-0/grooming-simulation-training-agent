#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
mkdir -p data models
.venv/bin/python scripts/get_llama_server.py || echo "NOTE: install llama.cpp manually (see message above)."
echo; echo "Setup done. Next:  .venv/bin/python scripts/download_model.py   then   scripts/run.sh"
