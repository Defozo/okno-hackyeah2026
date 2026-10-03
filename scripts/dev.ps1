$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:APP_ORIGIN = 'http://localhost:18430'
$env:COOKIE_SECURE = 'false'
& psst OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- ./.venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& psst OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- ./.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 18430 --no-access-log
