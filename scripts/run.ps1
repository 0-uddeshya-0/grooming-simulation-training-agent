# Run with:  powershell -ExecutionPolicy Bypass -File scripts\run.ps1   (add --cpu if the GPU/Vulkan start fails)
Set-Location "$PSScriptRoot\.."
& .\.venv\Scripts\python scripts\launch.py @args
