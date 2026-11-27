$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
python -m venv .venv
.\.venv\Scripts\pip install -q -r requirements.txt
New-Item -ItemType Directory -Force data, models | Out-Null
try { .\.venv\Scripts\python scripts\get_llama_server.py } catch { Write-Host "NOTE: install llama.cpp manually (see message above)." }
Write-Host "`nSetup done. Next:  .\.venv\Scripts\python scripts\download_model.py   then   scripts\run.ps1"
