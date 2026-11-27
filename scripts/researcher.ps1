# Run with:  powershell -ExecutionPolicy Bypass -File scripts\researcher.ps1
Set-Location "$PSScriptRoot\.."
& .\.venv\Scripts\python -m backend.researcher
