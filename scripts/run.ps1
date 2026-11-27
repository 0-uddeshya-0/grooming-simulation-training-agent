Set-Location "$PSScriptRoot\.."
$py = ".\.venv\Scripts\python"
& $py -m backend.preflight; if ($LASTEXITCODE -ne 0) { exit 1 }
$model = (Get-ChildItem models\*.gguf | Select-Object -First 1).FullName
$cfg = & $py -c "import yaml;c=yaml.safe_load(open('config/app.yaml'))['llama_server'];print(c['port'],c['ctx'])"
$port,$ctx = $cfg -split " "
$lp = Start-Process llama-server -ArgumentList "-m `"$model`" -c $ctx --host 127.0.0.1 --port $port -ngl 99" -PassThru -WindowStyle Hidden -RedirectStandardOutput data\llama.log
Start-Process "http://localhost:8000"
try { & $py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 } finally { Stop-Process -Id $lp.Id -ErrorAction SilentlyContinue }
