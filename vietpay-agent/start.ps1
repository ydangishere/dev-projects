Set-Location $PSScriptRoot
if (!(Test-Path '.venv')) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Write-Host "Open http://127.0.0.1:8000 after startup"
& .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
