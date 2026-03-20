Set-Location C:\dev\HelpChain.bg

# Optional: activate local venv for consistent Python/Flask resolution.
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
  & .\.venv\Scripts\Activate.ps1
}

$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$repoRoot = (Get-Location).Path
$preferredDb = Join-Path $repoRoot "instance\hc_local_dev.db"
$fallbackDb = Join-Path $repoRoot "backend\instance\app_clean.db"

# Local/dev profile
$env:FLASK_CONFIG = "dev"
$env:FLASK_DEBUG = "0"
$env:VOLUNTEER_DEV_BYPASS_ENABLED = "0"
$env:VOLUNTEER_DEV_BYPASS_EMAIL = ""

# Pick a healthy local DB and avoid booting against a schema-less file.
$dbCheck = @'
import sqlite3
import sys

path = sys.argv[1]
try:
    con = sqlite3.connect(path)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    ok = {"admin_users", "structures"}.issubset(tables)
    print("OK" if ok else "BROKEN")
except Exception:
    print("BROKEN")
'@

function Test-HealthyDb([string]$dbPath) {
  if (-not (Test-Path $dbPath)) {
    return $false
  }
  $result = & $python -c $dbCheck $dbPath 2>$null
  return (($result | Select-Object -Last 1).Trim() -eq "OK")
}

$selectedDb = $null
if (Test-HealthyDb $preferredDb) {
  $selectedDb = $preferredDb
} elseif (Test-HealthyDb $fallbackDb) {
  $selectedDb = $fallbackDb
  Write-Host "Primary local DB is not initialized. Falling back to app_clean.db." -ForegroundColor Yellow
} else {
  Write-Host "No healthy local database found." -ForegroundColor Red
  Write-Host "Run: .\.venv\Scripts\python.exe scripts\db_guard.py migrate" -ForegroundColor Yellow
  exit 1
}

$dbPosix = $selectedDb.Replace("\", "/")
$env:HC_DB_PATH = $dbPosix
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///$dbPosix"
$env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI
Remove-Item Env:SQLALCHEMY_DATABASE_URI -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///$dbPosix"
$env:DATABASE_URL = $env:SQLALCHEMY_DATABASE_URI

# Default local bind/port (magic links will point here unless PUBLIC_BASE_URL is set in .env)
$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "5000" }

# Lightweight diagnostics (no secrets printed)
$diag = @'
from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    print("DB:", app.config.get("SQLALCHEMY_DATABASE_URI"))
    print("MAIL_SERVER:", app.config.get("MAIL_SERVER"))
    print("MAIL_PORT:", app.config.get("MAIL_PORT"))
    print("MAIL_USERNAME:", app.config.get("MAIL_USERNAME"))
    print("MAIL_PASSWORD_SET:", bool(app.config.get("MAIL_PASSWORD")))
'@

Write-Host "Preparing HelpChain local server..." -ForegroundColor Cyan
& $python -c $diag

Write-Host ("Starting Flask on http://{0}:{1}" -f $bindHost, $port) -ForegroundColor Green
& $python -X utf8 run.py
