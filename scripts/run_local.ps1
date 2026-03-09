[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

$env:FLASK_APP = "backend.appy:app"
$env:FLASK_ENV = "development"
$hostIp = "127.0.0.1"
$port = 5005
$expectedDbUri = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
$expectedDbPath = "C:\dev\HelpChain.bg\backend\instance\app_clean.db"
$env:SQLALCHEMY_DATABASE_URI = $expectedDbUri
$env:HC_DB_PATH = $expectedDbPath

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $projectRoot
} elseif (-not ($env:PYTHONPATH -split ';' | Where-Object { $_ -eq $projectRoot })) {
    $env:PYTHONPATH = "$projectRoot;$($env:PYTHONPATH)"
}

$appEntryPoint = $env:FLASK_APP

$probeCode = @'
import json
from backend.appy import app
from backend.extensions import db
from sqlalchemy import inspect

uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
instance = getattr(app, "instance_path", "") or ""
req_exists = None
admin_exists = None

with app.app_context():
    try:
        tables = set(inspect(db.engine).get_table_names())
        req_exists = "requests" in tables
        admin_exists = "admin_users" in tables
    except Exception:
        pass

print(
    json.dumps(
        {
            "uri": uri,
            "instance_path": instance,
            "requests_exists": req_exists,
            "admin_users_exists": admin_exists,
        }
    )
)
'@

$probeOut = [System.IO.Path]::GetTempFileName()
$probeErr = [System.IO.Path]::GetTempFileName()
$probePy = Join-Path $projectRoot ".hc_runtime_probe_tmp.py"

try {
    Set-Content -Path $probePy -Value $probeCode -Encoding UTF8
    $probeProc = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @($probePy) `
        -WorkingDirectory $projectRoot `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $probeOut `
        -RedirectStandardError $probeErr
} finally {
    $probeStdout = if (Test-Path $probeOut) { Get-Content $probeOut -Raw } else { "" }
    $probeStderr = if (Test-Path $probeErr) { Get-Content $probeErr -Raw } else { "" }
    if (Test-Path $probeOut) { Remove-Item $probeOut -Force -ErrorAction SilentlyContinue }
    if (Test-Path $probeErr) { Remove-Item $probeErr -Force -ErrorAction SilentlyContinue }
    if (Test-Path $probePy) { Remove-Item $probePy -Force -ErrorAction SilentlyContinue }
}

if (-not $probeProc -or $probeProc.ExitCode -ne 0) {
    Write-Host "APP IMPORT FAILED" -ForegroundColor Red
    if (-not [string]::IsNullOrWhiteSpace($probeStderr)) {
        Write-Host ("REASON: {0}" -f $probeStderr.Trim()) -ForegroundColor Red
    } elseif (-not [string]::IsNullOrWhiteSpace($probeStdout)) {
        Write-Host ("REASON: {0}" -f $probeStdout.Trim()) -ForegroundColor Red
    } else {
        Write-Host "REASON: unknown import error" -ForegroundColor Red
    }
    exit 1
}

$stdoutLines = @($probeStdout -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($stdoutLines.Count -eq 0) {
    Write-Host "APP IMPORT FAILED" -ForegroundColor Red
    Write-Host "REASON: runtime probe returned empty output" -ForegroundColor Red
    exit 1
}

try {
    $runtime = $stdoutLines[-1] | ConvertFrom-Json
} catch {
    Write-Host "APP IMPORT FAILED" -ForegroundColor Red
    Write-Host ("REASON: invalid runtime probe JSON. RAW STDOUT: {0}" -f $probeStdout.Trim()) -ForegroundColor Red
    if (-not [string]::IsNullOrWhiteSpace($probeStderr)) {
        Write-Host ("STDERR: {0}" -f $probeStderr.Trim()) -ForegroundColor Red
    }
    exit 1
}

$dbUri = [string]$runtime.uri
$instancePath = [string]$runtime.instance_path

$line = "=" * 50
Write-Host $line
Write-Host "HELPCHAIN LOCAL DEV"
Write-Host "APP: $appEntryPoint"
Write-Host "DB: $dbUri"
Write-Host "INSTANCE: $instancePath"
Write-Host "HOST: $hostIp"
Write-Host "PORT: $port"
if ($null -ne $runtime.requests_exists) {
    Write-Host ("requests table exists: {0}" -f ($(if ($runtime.requests_exists) { "yes" } else { "no" })))
}
if ($null -ne $runtime.admin_users_exists) {
    Write-Host ("admin_users table exists: {0}" -f ($(if ($runtime.admin_users_exists) { "yes" } else { "no" })))
}
Write-Host $line

if ([string]::IsNullOrWhiteSpace($dbUri)) {
    Write-Host "WARNING: SQLALCHEMY_DATABASE_URI is empty." -ForegroundColor Yellow
} elseif ($dbUri -eq "sqlite:///:memory:") {
    Write-Host "WARNING: SQLALCHEMY_DATABASE_URI points to in-memory sqlite (suspicious for local dev)." -ForegroundColor Yellow
} elseif ($dbUri -match "tmp|temp") {
    Write-Host "WARNING: SQLALCHEMY_DATABASE_URI points to a temp path (suspicious for local dev)." -ForegroundColor Yellow
} elseif ($dbUri -ne $expectedDbUri) {
    Write-Host "WARNING: SQLALCHEMY_DATABASE_URI differs from expected canonical local DB." -ForegroundColor Yellow
    Write-Host "EXPECTED: $expectedDbUri" -ForegroundColor Yellow
}

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$primaryLogFile = Join-Path $logDir "helpchain-dev.log"
$logFile = $primaryLogFile
$timestampLogFile = Join-Path $logDir ("helpchain-dev-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    try {
        Write-Host "LOG: $logFile"
        & $pythonExe -m flask run --host $hostIp --port $port 2>&1 | Tee-Object -FilePath $logFile -Append -ErrorAction Stop
        $exitCode = $LASTEXITCODE
    }
    catch {
        Write-Host "WARNING: log file is busy, falling back to session log file." -ForegroundColor Yellow
        $logFile = $timestampLogFile
        try {
            Write-Host "LOG: $logFile"
            & $pythonExe -m flask run --host $hostIp --port $port 2>&1 | Tee-Object -FilePath $logFile -Append -ErrorAction Stop
            $exitCode = $LASTEXITCODE
        }
        catch {
            Write-Host "WARNING: log file is busy, falling back to console-only output." -ForegroundColor Yellow
            & $pythonExe -m flask run --host $hostIp --port $port
            $exitCode = $LASTEXITCODE
        }
    }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
exit $exitCode
