# Run with:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$pyArgs = if ($py -eq "py") { @("-3") } else { @() }
& $py @pyArgs -m venv .venv; if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment. Install Python 3.10+ from python.org (tick 'Add to PATH')." }
& .\.venv\Scripts\python -m pip install -q -r requirements.txt; if ($LASTEXITCODE -ne 0) { throw "pip install failed (internet needed once)." }
New-Item -ItemType Directory -Force data, models | Out-Null
& .\.venv\Scripts\python scripts\get_llama_server.py
if ($LASTEXITCODE -ne 0) { Write-Host "NOTE: install llama.cpp manually (see message above)." }
Write-Host "`nSetup done. Next:  .\.venv\Scripts\python scripts\download_model.py   then   powershell -ExecutionPolicy Bypass -File scripts\run.ps1"
