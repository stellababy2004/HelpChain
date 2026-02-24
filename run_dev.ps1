Set-Location C:\dev\HelpChain.bg
& .\.venv\Scripts\Activate.ps1

$env:FLASK_CONFIG = "dev"
$env:FLASK_DEBUG = "1"

Copy-Item .\instance\hc_dev.db .\instance\hc_run.db -Force
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///C:/dev/HelpChain.bg/instance/hc_run.db"
$env:HC_DB_PATH = "C:/dev/HelpChain.bg/instance/hc_run.db"
# Prevent inherited shell env from overriding the dev DB target (Config prefers DATABASE_URL/HC_DB_PATH)
$env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI

& .\.venv\Scripts\python.exe -m flask --app backend.helpchain_backend.src.app:create_app run --no-reload --port 5005

# If you still see "disk I/O error", use this "iron" fallback (TEMP DB):
# Copy-Item .\instance\hc_dev.db "$env:TEMP\hc_run.db" -Force
# $env:SQLALCHEMY_DATABASE_URI = "sqlite:///$env:TEMP/hc_run.db"
# $env:HC_DB_PATH = "$env:TEMP/hc_run.db"
# $env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI
# & .\.venv\Scripts\python.exe -m flask --app backend.helpchain_backend.src.app:create_app run --no-reload --port 5005

