Set-Location C:\dev\HelpChain.bg
& .\.venv\Scripts\Activate.ps1

$env:FLASK_CONFIG = "dev"
$env:FLASK_DEBUG = "1"

Copy-Item .\instance\hc_dev.db .\instance\hc_run.db -Force
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///C:/dev/HelpChain.bg/instance/hc_run.db"
$env:HC_DB_PATH = "C:/dev/HelpChain.bg/instance/hc_run.db"
# Prevent inherited shell env from overriding the dev DB target (Config prefers DATABASE_URL/HC_DB_PATH)
$env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI

Write-Host "Starting HelpChain dev server on http://127.0.0.1:5005" -ForegroundColor Cyan
Write-Host ("DB (SQLALCHEMY_DATABASE_URI): {0}" -f $env:SQLALCHEMY_DATABASE_URI) -ForegroundColor DarkCyan
Write-Host ("DB (HC_DB_PATH): {0}" -f $env:HC_DB_PATH) -ForegroundColor DarkCyan

& .\.venv\Scripts\python.exe -m flask --app backend.helpchain_backend.src.app:create_app run --no-reload --port 5005

# If you still see "disk I/O error", use this "iron" fallback (TEMP DB):
# Copy-Item .\instance\hc_dev.db "$env:TEMP\hc_run.db" -Force
# $env:SQLALCHEMY_DATABASE_URI = "sqlite:///$env:TEMP/hc_run.db"
# $env:HC_DB_PATH = "$env:TEMP/hc_run.db"
# $env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI
# & .\.venv\Scripts\python.exe -m flask --app backend.helpchain_backend.src.app:create_app run --no-reload --port 5005

