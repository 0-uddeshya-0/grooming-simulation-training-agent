$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
python -m venv .venv
.\.venv\Scripts\pip install -q -r requirements.txt
New-Item -ItemType Directory -Force data, models | Out-Null
if (-not (Get-Command llama-server -ErrorAction SilentlyContinue)) { Write-Host "NOTE: llama-server not found. Get the Vulkan build from https://github.com/ggml-org/llama.cpp/releases and add it to PATH." }
Write-Host "Setup done. Next: .\.venv\Scripts\python scripts\download_model.py ; scripts\run.ps1"
