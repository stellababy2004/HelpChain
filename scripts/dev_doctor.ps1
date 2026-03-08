param()

$ErrorActionPreference = "Stop"
$script:WarnCount = 0

function Write-Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    $script:WarnCount += 1
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Stop-CoreFail([string]$Message, [string]$Reason) {
    Write-Fail $Message
    if (-not [string]::IsNullOrWhiteSpace($Reason)) {
        Write-Fail "Reason: $Reason"
    }
    Write-Host ""
    Write-Host "DEV DOCTOR RESULT: FAIL" -ForegroundColor Red
    exit 1
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$appEntrypoint = "backend.appy:app"
$expectedDbUri = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Write-Host "HELPCHAIN DEV DOCTOR" -ForegroundColor Cyan
Write-Host "Started: $startedAt"
Write-Host ""

try {
    $gitBranch = (& git -C $projectRoot rev-parse --abbrev-ref HEAD 2>$null | Select-Object -First 1).Trim()
} catch {
    $gitBranch = ""
}
if ([string]::IsNullOrWhiteSpace($gitBranch)) {
    Write-Warn "Git branch: unavailable"
} else {
    Write-Host "Git branch: $gitBranch"
}

try {
    $gitSha = (& git -C $projectRoot rev-parse --short HEAD 2>$null | Select-Object -First 1).Trim()
} catch {
    $gitSha = ""
}
if ([string]::IsNullOrWhiteSpace($gitSha)) {
    Write-Warn "Git commit: unavailable"
} else {
    Write-Host "Git commit: $gitSha"
}
Write-Host ""

if (-not (Test-Path $pythonExe)) {
    Stop-CoreFail "Python executable missing: $pythonExe" "Create/activate .venv first."
}
Write-Pass "Python executable found: $pythonExe"

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $projectRoot
} elseif (-not ($env:PYTHONPATH -split ';' | Where-Object { $_ -eq $projectRoot })) {
    $env:PYTHONPATH = "$projectRoot;$($env:PYTHONPATH)"
}

$probeCode = @'
import json
import os

from sqlalchemy import inspect, text

result = {
    "app_entrypoint": "backend.appy:app",
    "app_import_ok": False,
    "sqlalchemy_database_uri": None,
    "instance_path": None,
    "env_mode": None,
    "tables": {
        "requests_exists": None,
        "admin_users_exists": None,
        "requests_count": None,
        "admin_users_count": None,
        "admin_user_present": None,
    },
    "routes": {
        "/": False,
        "/admin/requests": False,
        "/admin/pilotage": False,
    },
    "security": {
        "csp_configured": False,
        "security_headers_config_present": False,
    },
    "mail": {
        "configured": False,
    },
    "migration": {
        "db_revision": None,
        "head_revision": None,
        "status": "UNKNOWN",
    },
    "errors": [],
}

try:
    from backend.appy import app
    from backend.models import db
except Exception as exc:
    print(json.dumps({
        "fatal": True,
        "message": "APP IMPORT FAILED",
        "reason": str(exc),
    }))
    raise SystemExit(2)

result["app_import_ok"] = True

try:
    with app.app_context():
        result["sqlalchemy_database_uri"] = app.config.get("SQLALCHEMY_DATABASE_URI")
        result["instance_path"] = getattr(app, "instance_path", None)
        result["env_mode"] = (
            app.config.get("ENV")
            or app.config.get("FLASK_ENV")
            or os.getenv("FLASK_ENV")
            or os.getenv("HC_ENV")
            or "unknown"
        )

        try:
            tables = set(inspect(db.engine).get_table_names())
            req_exists = "requests" in tables
            adm_exists = "admin_users" in tables

            result["tables"]["requests_exists"] = req_exists
            result["tables"]["admin_users_exists"] = adm_exists

            if req_exists:
                result["tables"]["requests_count"] = int(
                    db.session.execute(text("SELECT COUNT(*) FROM requests")).scalar_one()
                )
            if adm_exists:
                admin_count = int(
                    db.session.execute(text("SELECT COUNT(*) FROM admin_users")).scalar_one()
                )
                result["tables"]["admin_users_count"] = admin_count
                result["tables"]["admin_user_present"] = admin_count > 0
        except Exception as exc:
            result["errors"].append(f"DB inspection warning: {exc}")

        try:
            rules = {r.rule for r in app.url_map.iter_rules()}
            result["routes"]["/"] = "/" in rules
            result["routes"]["/admin/requests"] = "/admin/requests" in rules
            result["routes"]["/admin/pilotage"] = "/admin/pilotage" in rules
        except Exception as exc:
            result["errors"].append(f"Route inspection warning: {exc}")

        try:
            csp_cfg = app.config.get("CONTENT_SECURITY_POLICY")
            talisman_ext = "talisman" in getattr(app, "extensions", {})
            result["security"]["csp_configured"] = bool(csp_cfg) or talisman_ext
            result["security"]["security_headers_config_present"] = bool(
                talisman_ext
                or app.config.get("SESSION_COOKIE_SECURE")
                or app.config.get("REMEMBER_COOKIE_SECURE")
                or app.config.get("PREFERRED_URL_SCHEME")
            )
        except Exception as exc:
            result["errors"].append(f"Security inspection warning: {exc}")

        try:
            mail_server = app.config.get("MAIL_SERVER")
            mail_sender = app.config.get("MAIL_DEFAULT_SENDER")
            result["mail"]["configured"] = bool(mail_server and mail_sender)
        except Exception as exc:
            result["errors"].append(f"Mail inspection warning: {exc}")

        try:
            db_revisions = []
            if "alembic_version" in tables:
                rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                db_revisions = sorted({str(row[0]).strip() for row in rows if row and row[0]})
            if db_revisions:
                result["migration"]["db_revision"] = ",".join(db_revisions)

            head_revisions = []
            try:
                from alembic.config import Config
                from alembic.script import ScriptDirectory

                cfg = Config()
                cfg.set_main_option("script_location", "migrations")
                script = ScriptDirectory.from_config(cfg)
                head_revisions = sorted(script.get_heads() or [])
            except Exception as exc:
                result["errors"].append(f"Alembic head warning: {exc}")

            if head_revisions:
                result["migration"]["head_revision"] = ",".join(head_revisions)

            if db_revisions and head_revisions:
                if set(db_revisions) == set(head_revisions):
                    result["migration"]["status"] = "OK"
                else:
                    result["migration"]["status"] = "OUT OF DATE"
            else:
                result["migration"]["status"] = "UNKNOWN"
        except Exception as exc:
            result["errors"].append(f"Migration inspection warning: {exc}")

except Exception as exc:
    result["errors"].append(f"Runtime warning: {exc}")

print(json.dumps(result))
'@

$probePy = Join-Path $projectRoot ".hc_dev_doctor_probe_tmp.py"
$probeOut = [System.IO.Path]::GetTempFileName()
$probeErr = [System.IO.Path]::GetTempFileName()

try {
    Set-Content -Path $probePy -Value $probeCode -Encoding UTF8
    $proc = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @($probePy) `
        -WorkingDirectory $projectRoot `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $probeOut `
        -RedirectStandardError $probeErr

    $stdoutRaw = if (Test-Path $probeOut) { Get-Content $probeOut -Raw } else { "" }
    $stderrRaw = if (Test-Path $probeErr) { Get-Content $probeErr -Raw } else { "" }
}
finally {
    if (Test-Path $probePy) { Remove-Item $probePy -Force -ErrorAction SilentlyContinue }
    if (Test-Path $probeOut) { Remove-Item $probeOut -Force -ErrorAction SilentlyContinue }
    if (Test-Path $probeErr) { Remove-Item $probeErr -Force -ErrorAction SilentlyContinue }
}

$stdoutLines = @($stdoutRaw -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($stdoutLines.Count -eq 0) {
    $reason = if (-not [string]::IsNullOrWhiteSpace($stderrRaw)) { $stderrRaw.Trim() } else { "runtime probe returned no output" }
    Stop-CoreFail "APP IMPORT FAILED" $reason
}

try {
    $payload = $stdoutLines[-1] | ConvertFrom-Json
}
catch {
    Stop-CoreFail "APP IMPORT FAILED" ("invalid probe output: {0}" -f $stdoutLines[-1])
}

if ($payload.fatal -eq $true) {
    Stop-CoreFail $payload.message $payload.reason
}

Write-Host ""
if ($payload.app_import_ok) {
    Write-Pass "APP IMPORT OK"
} else {
    Stop-CoreFail "APP IMPORT FAILED" ""
}

Write-Host ""
Write-Host "Runtime"
Write-Host "APP: $($payload.app_entrypoint)"
Write-Host "DB: $($payload.sqlalchemy_database_uri)"
Write-Host "CANONICAL_DB: $expectedDbUri"
Write-Host "INSTANCE: $($payload.instance_path)"
Write-Host "ENV: $($payload.env_mode)"
Write-Host ""

$dbUri = [string]($payload.sqlalchemy_database_uri)
if ($dbUri -ne $expectedDbUri) {
    Write-Warn "Runtime DB differs from canonical local DB target."
}
if ($dbUri -match "hc_local_dev\.db|volunteers\.db|instance/app\.db|hc_run\.db") {
    Write-Warn "Runtime DB matches a known legacy/non-canonical sqlite path."
}

if ($payload.tables.requests_exists) { Write-Pass "requests table: yes" } else { Write-Warn "requests table: no" }
if ($payload.tables.admin_users_exists) { Write-Pass "admin_users table: yes" } else { Write-Warn "admin_users table: no" }

if ($null -ne $payload.tables.requests_count) { Write-Host ("requests count: {0}" -f $payload.tables.requests_count) }
if ($null -ne $payload.tables.admin_users_count) { Write-Host ("admin_users count: {0}" -f $payload.tables.admin_users_count) }

if ($null -ne $payload.tables.admin_user_present) {
    if ($payload.tables.admin_user_present) { Write-Pass "admin user present: yes" } else { Write-Warn "admin user present: no" }
}

Write-Host ""
if ($payload.routes.'/') { Write-Pass "route present (/): yes" } else { Write-Warn "route present (/): no" }
if ($payload.routes.'/admin/requests') { Write-Pass "route present (/admin/requests): yes" } else { Write-Warn "route present (/admin/requests): no" }
if ($payload.routes.'/admin/pilotage') { Write-Pass "route present (/admin/pilotage): yes" } else { Write-Warn "route present (/admin/pilotage): no" }

if ($payload.security.csp_configured) { Write-Pass "CSP configured: yes" } else { Write-Warn "CSP configured: no" }
if ($payload.security.security_headers_config_present) { Write-Pass "security headers config present: yes" } else { Write-Warn "security headers config present: no" }

if ($payload.mail.configured) { Write-Pass "mail config: configured" } else { Write-Warn "mail config: missing" }

Write-Host ""
Write-Host "DB migration revision: $($payload.migration.db_revision)"
Write-Host "Head revision: $($payload.migration.head_revision)"
if ($payload.migration.status -eq "OK") {
    Write-Pass "Migration status: OK"
} elseif ($payload.migration.status -eq "OUT OF DATE") {
    Write-Warn "Migration status: OUT OF DATE"
} else {
    Write-Warn "Migration status: UNKNOWN"
}

if ($payload.errors -and $payload.errors.Count -gt 0) {
    Write-Host ""
    foreach ($err in $payload.errors) {
        Write-Warn $err
    }
}

Write-Host ""
Write-Host "Next recommended command:"
Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1"

Write-Host ""
if ($script:WarnCount -gt 0) {
    Write-Host "DEV DOCTOR RESULT: OK WITH WARNINGS" -ForegroundColor Yellow
} else {
    Write-Host "DEV DOCTOR RESULT: OK" -ForegroundColor Green
}

exit 0
