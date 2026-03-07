Set-Location C:\dev\HelpChain.bg

# Optional: activate local venv for consistent Python/Flask resolution.
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
  & .\.venv\Scripts\Activate.ps1
}

$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

# Local/dev profile
$env:FLASK_CONFIG = "dev"
$env:FLASK_DEBUG = "0"
$env:VOLUNTEER_DEV_BYPASS_ENABLED = "0"
$env:VOLUNTEER_DEV_BYPASS_EMAIL = ""

# Force a single stable local DB (avoid random drift between copies).
$env:HC_DB_PATH = "C:/dev/HelpChain.bg/instance/hc_local_dev.db"
Remove-Item Env:SQLALCHEMY_DATABASE_URI -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

# Default local bind/port (magic links will point here unless PUBLIC_BASE_URL is set in .env)
$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "5000" }

# Lightweight diagnostics (no secrets printed)
$diag = @"
from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    print("DB:", app.config.get("SQLALCHEMY_DATABASE_URI"))
    print("MAIL_SERVER:", app.config.get("MAIL_SERVER"))
    print("MAIL_PORT:", app.config.get("MAIL_PORT"))
    print("MAIL_USERNAME:", app.config.get("MAIL_USERNAME"))
    print("MAIL_PASSWORD_SET:", bool(app.config.get("MAIL_PASSWORD")))
"@

Write-Host "Preparing HelpChain local server..." -ForegroundColor Cyan
& $python -c $diag

Write-Host ("Starting Flask on http://{0}:{1}" -f $bindHost, $port) -ForegroundColor Green
& $python -X utf8 run.py
