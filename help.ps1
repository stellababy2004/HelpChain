param(
  [int]$Port = 5005,
  [string]$AdminUser = "admin",
  [string]$AdminPassword = "Admin123!"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "HelpChain local launcher" -ForegroundColor Cyan
Write-Host "------------------------" -ForegroundColor Cyan

Set-Location "C:\dev\HelpChain"

$env:FLASK_APP = "backend.appy:app"
$env:HC_SKIP_SELFHEAL = "0"
$env:HC_LOCAL_DEV = "1"
$env:REQUIRE_ADMIN_MFA = "false"

Write-Host "Stopping old Python processes..." -ForegroundColor Yellow
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

Write-Host "Checking local database..." -ForegroundColor Yellow

$dbOk = @"
import sqlite3
import os

db = "instance/hc_local_dev.db"

if not os.path.exists(db):
    print("NO")
else:
    try:
        con = sqlite3.connect(db)
        rows = con.execute("""
            select name
            from sqlite_master
            where type='table'
            and name in ('structures','analytics_events','admin_users')
        """).fetchall()
        found = {r[0] for r in rows}
        required = {"structures", "analytics_events", "admin_users"}
        print("YES" if required.issubset(found) else "NO")
    except Exception:
        print("NO")
"@ | .\.venv\Scripts\python.exe

if ($dbOk.Trim() -ne "YES") {
  Write-Host "Database is missing required tables. Rebuilding local DB..." -ForegroundColor Red

  Remove-Item .\instance\hc_local_dev.db -Force -ErrorAction SilentlyContinue
  Remove-Item .\instance\hc_local_dev.db-* -Force -ErrorAction SilentlyContinue

  .\.venv\Scripts\python.exe -m flask db stamp base
  .\.venv\Scripts\python.exe -m flask db upgrade
}
else {
  Write-Host "Database schema looks OK." -ForegroundColor Green
}

Write-Host "Ensuring admin user exists..." -ForegroundColor Yellow

$adminScript = @"
from backend.appy import app
from backend.extensions import db
from backend.models import AdminUser

with app.app_context():
    username = "$AdminUser"
    password = "$AdminPassword"

    u = AdminUser.query.filter_by(username=username).first()

    if not u:
        u = AdminUser(
            username=username,
            email="admin@localhost",
            role="superadmin",
            is_active=True
        )
        db.session.add(u)

    u.email = "admin@localhost"
    u.role = "superadmin"
    u.is_active = True
    u.set_password(password)

    for field in ["mfa_enabled", "must_change_password", "is_locked"]:
        if hasattr(u, field):
            setattr(u, field, False)

    for field in ["failed_login_attempts", "login_attempts"]:
        if hasattr(u, field):
            setattr(u, field, 0)

    for field in ["locked_until", "lock_until"]:
        if hasattr(u, field):
            setattr(u, field, None)

    db.session.commit()

    print("Admin ready: " + username + " / " + password)
"@

$adminScript | .\.venv\Scripts\python.exe

Write-Host ""
Write-Host "Starting HelpChain on http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "Admin: $AdminUser / $AdminPassword" -ForegroundColor Green
Write-Host ""

.\.venv\Scripts\python.exe -m flask --app backend.appy:app run --host 127.0.0.1 --port $Port --debug
