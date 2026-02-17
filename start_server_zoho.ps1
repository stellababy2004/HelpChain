Set-Location C:\dev\HelpChain.bg

# Optional: activate venv if present (keeps python/flask consistent).
if (Test-Path ".\\.venv\\Scripts\\Activate.ps1") {
  & .\\.venv\\Scripts\\Activate.ps1
}

$python = if (Test-Path ".\\.venv\\Scripts\\python.exe") { ".\\.venv\\Scripts\\python.exe" } else { "python" }

$env:FLASK_CONFIG = "dev"
$env:FLASK_DEBUG = "0"
# Disable dev volunteer bypass during real flow testing.
$env:VOLUNTEER_DEV_BYPASS_ENABLED = "0"
$env:VOLUNTEER_DEV_BYPASS_EMAIL = ""

# Zoho SMTP (safe to keep non-secret defaults here; password is prompted)
$env:MAIL_SERVER = "smtp.zoho.eu"
$env:MAIL_PORT = "587"
$env:MAIL_USE_TLS = "1"
$env:MAIL_USE_SSL = "0"
$env:MAIL_USERNAME = "contact@helpchain.live"
$env:MAIL_DEFAULT_SENDER = "contact@helpchain.live"
$env:PRO_LEADS_NOTIFY_TO = "contact@helpchain.live"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:5005"
$env:HC_DB_PATH = "C:/dev/HelpChain.bg/instance/hc_run_canon.db"
# Ensure legacy DB env vars cannot override HC_DB_PATH.
Remove-Item Env:SQLALCHEMY_DATABASE_URI -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

$sec = Read-Host "Zoho App Password" -AsSecureString
$env:MAIL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
)

# Keep runtime DB stable and avoid corrupted legacy instance DB by using HC_DB_PATH.
if (-not $env:HC_DB_PATH) {
  $env:SQLALCHEMY_DATABASE_URI = "sqlite:///C:/dev/HelpChain.bg/instance/hc_run.db"
}

$port = if ($env:PORT) { $env:PORT } else { "5005" }
# $Host is a built-in read-only PowerShell variable; use a different name.
$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }

Write-Host ("ENV: MAIL_SERVER={0} MAIL_PORT={1} MAIL_USERNAME={2} MAIL_PASSWORD_SET={3}" -f `
  $env:MAIL_SERVER, $env:MAIL_PORT, $env:MAIL_USERNAME, ([bool]$env:MAIL_PASSWORD))
Write-Host ("DB: HC_DB_PATH={0} SQLALCHEMY_DATABASE_URI={1}" -f $env:HC_DB_PATH, $env:SQLALCHEMY_DATABASE_URI)

$diag = @"
import os
from backend.helpchain_backend.src.app import create_app
app = create_app()
print('ENV=', os.environ.get('MAIL_SERVER'), os.environ.get('MAIL_PORT'), os.environ.get('MAIL_USERNAME'), bool(os.environ.get('MAIL_PASSWORD')))
print('CFG=', app.config.get('MAIL_SERVER'), app.config.get('MAIL_PORT'), app.config.get('MAIL_USERNAME'), bool(app.config.get('MAIL_PASSWORD')))
print('DB =', app.config.get('SQLALCHEMY_DATABASE_URI'))
"@

Write-Host "Running ENV vs CFG diag..."
& $python -c $diag

Write-Host ("Starting Flask on http://{0}:{1}" -f $bindHost, $port)
& $python -m flask --app backend.helpchain_backend.src.app:create_app run --no-reload --host $bindHost --port $port
