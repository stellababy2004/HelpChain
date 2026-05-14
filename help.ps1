param(
  [int]$Port = 5005,
  [string]$AdminUser = "admin",
  [string]$AdminPassword = "Admin123!"
)

$ErrorActionPreference = "Stop"

$Root = "C:\dev\HelpChain"
$InstanceDir = Join-Path $Root "instance"
$LocalDbPath = Join-Path $InstanceDir "hc_local_dev.db"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$SeedScript = Join-Path $Root "scripts\seed_local_demo.py"
$RequiredTables = @(
  "admin_users",
  "structures",
  "users",
  "requests",
  "cases",
  "case_events",
  "alembic_version"
)

Set-Location $Root
New-Item -ItemType Directory -Path $InstanceDir -Force | Out-Null

# Force local Windows development settings. Do not inherit production/Render/Neon values here.
$env:PUBLIC_BASE_URL = "http://127.0.0.1:5005"
$env:DATABASE_URL = "sqlite:///C:/dev/HelpChain/instance/hc_local_dev.db"
$env:HC_DB_PATH = $LocalDbPath
$env:FLASK_APP = "backend.appy:app"
$env:HC_SKIP_SELFHEAL = "1"
$env:HC_LOCAL_DEV = "1"
$env:REQUIRE_ADMIN_MFA = "false"
$env:HC_LOCAL_ADMIN_USER = $AdminUser
$env:HC_LOCAL_ADMIN_PASSWORD = $AdminPassword
$env:HC_DEMO_ADMIN_PASSWORD = $AdminPassword

if (-not (Test-Path $Python)) {
  throw "Python virtualenv not found at $Python"
}

function Invoke-PythonBlock {
  param([Parameter(Mandatory = $true)][string]$Code)

  $output = $Code | & $Python
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed."
  }
  return $output
}

function Test-IsAllowedLocalDbPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  $normalized = $Path.Replace("/", "\").ToLowerInvariant()
  return (
    $normalized.Contains("c:\dev\helpchain\instance\hc_local_dev.db") -or
    $normalized.EndsWith("instance\hc_local_dev.db")
  )
}

function Stop-LocalPythonProcesses {
  Write-Host "Stopping Python processes..."
  Stop-Process -Name python -Force -ErrorAction SilentlyContinue
}

function Test-DatabaseSchema {
  $tablesCsv = ($RequiredTables -join ",")
  $script = @"
import os
import sqlite3
import sys

db_path = os.environ.get("HC_DB_PATH", "")
required = set("$tablesCsv".split(","))

if not db_path:
    print("NO missing=all reason=HC_DB_PATH_not_set")
    sys.exit(0)

try:
    con = sqlite3.connect(db_path)
    rows = con.execute("select name from sqlite_master where type='table'").fetchall()
    existing = {row[0] for row in rows}
    missing = sorted(required - existing)
    con.close()
except Exception as exc:
    print(f"NO missing=unknown error={exc}")
    sys.exit(0)

if missing:
    print("NO missing=" + ",".join(missing))
else:
    print("YES")
"@

  $result = (Invoke-PythonBlock $script | Select-Object -Last 1).Trim()
  if ($result -eq "YES") {
    return $true
  }

  Write-Host "Schema check failed: $result" -ForegroundColor Yellow
  return $false
}

function Invoke-FlaskMigrations {
  Write-Host "Running migrations..." -ForegroundColor Yellow
  & $Python -m flask db upgrade
  if ($LASTEXITCODE -ne 0) {
    throw "Flask migrations failed."
  }
}

function Remove-LocalDatabase {
  if (-not (Test-IsAllowedLocalDbPath $LocalDbPath)) {
    throw "Refusing to delete database because path is not the guarded local SQLite DB: $LocalDbPath"
  }

  if (-not (Test-Path $LocalDbPath)) {
    return
  }

  try {
    Remove-Item -Path $LocalDbPath -Force
  } catch {
    Write-Host "Close all Python/Flask processes and delete instance/hc_local_dev.db manually." -ForegroundColor Red
    exit 1
  }
}

function Test-AdminExists {
  $script = @"
import os
import sqlite3

db_path = os.environ.get("HC_DB_PATH", "")
username = os.environ.get("HC_LOCAL_ADMIN_USER", "admin")

try:
    con = sqlite3.connect(db_path)
    row = con.execute(
        "select 1 from admin_users where lower(username) = lower(?) limit 1",
        (username,),
    ).fetchone()
    con.close()
except Exception:
    print("NO")
else:
    print("YES" if row else "NO")
"@

  $result = (Invoke-PythonBlock $script | Select-Object -Last 1).Trim()
  return ($result -eq "YES")
}

function Invoke-LocalSeed {
  if (-not (Test-Path $SeedScript)) {
    Write-Host "Local seed script not found; continuing with admin bootstrap."
    return
  }

  Write-Host "Seeding local demo/admin..."
  & $Python $SeedScript --reset-demo
  if ($LASTEXITCODE -ne 0) {
    throw "Local seed script failed."
  }
}

function Ensure-LocalAdmin {
  $script = @"
import os

from backend.appy import app
from backend.extensions import db
from backend.models import AdminUser

username = os.environ.get("HC_LOCAL_ADMIN_USER", "admin")
password = os.environ.get("HC_LOCAL_ADMIN_PASSWORD", "Admin123!")

with app.app_context():
    user = AdminUser.query.filter_by(username=username).first()
    if user is None:
        user = AdminUser(username=username, email=f"{username}@localhost", role="superadmin")
        db.session.add(user)

    if hasattr(user, "email"):
        user.email = f"{username}@localhost"
    if hasattr(user, "role"):
        user.role = "superadmin"
    if hasattr(user, "is_active"):
        user.is_active = True
    if hasattr(user, "mfa_enabled"):
        user.mfa_enabled = False
    if hasattr(user, "mfa_secret"):
        user.mfa_secret = None
    if hasattr(user, "must_change_password"):
        user.must_change_password = False
    if hasattr(user, "is_locked"):
        user.is_locked = False
    if hasattr(user, "failed_login_attempts"):
        user.failed_login_attempts = 0
    if hasattr(user, "login_attempts"):
        user.login_attempts = 0
    if hasattr(user, "locked_until"):
        user.locked_until = None
    if hasattr(user, "lock_until"):
        user.lock_until = None

    user.set_password(password)
    db.session.commit()
"@

  Invoke-PythonBlock $script | Out-Null
}

Stop-LocalPythonProcesses

Write-Host "Checking local database..."
$databaseRecreated = $false

if (Test-DatabaseSchema) {
  Write-Host "Database schema OK" -ForegroundColor Green
} else {
  Remove-LocalDatabase
  $databaseRecreated = $true
  Invoke-FlaskMigrations

  if (-not (Test-DatabaseSchema)) {
    throw "Database schema is still incomplete after migrations."
  }

  Write-Host "Database schema OK" -ForegroundColor Green
  Write-Host "Local DB repaired" -ForegroundColor Green
}

$adminMissing = -not (Test-AdminExists)
if ($databaseRecreated -or $adminMissing) {
  Invoke-LocalSeed
}

Ensure-LocalAdmin
Write-Host "Admin ready: $AdminUser / $AdminPassword" -ForegroundColor Green

Write-Host "Starting HelpChain on http://127.0.0.1:$Port ..."
& $Python -m flask --app backend.appy:app run --host 127.0.0.1 --port $Port --debug
