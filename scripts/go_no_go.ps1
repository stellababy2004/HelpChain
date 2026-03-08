param()

$ErrorActionPreference = "Stop"

function Write-Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$warnings = 0
$appEntrypoint = "backend.appy:app"
$canonicalDb = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"

Write-Host "HELPCHAIN GO / NO-GO CHECK" -ForegroundColor Cyan
Write-Host "Started: $startedAt"
Write-Host "APP: $appEntrypoint"
Write-Host "CANONICAL DB: $canonicalDb"
Write-Host ""

Write-Host "Step 1/3 - Dev doctor" -ForegroundColor Cyan
$doctorScript = Join-Path $projectRoot "scripts\dev_doctor.ps1"
$doctorOutput = & powershell -ExecutionPolicy Bypass -File $doctorScript 2>&1
$doctorExitCode = $LASTEXITCODE
foreach ($line in $doctorOutput) {
    Write-Host "$line"
}
if ($doctorExitCode -ne 0) {
    Write-Host ""
    Write-Fail "FINAL RESULT: NO-GO"
    Write-Fail "Reason: dev_doctor failed"
    Write-Host "Recommended next action: inspect dev_doctor output and fix core boot issues."
    exit 1
}
if ($doctorOutput -match "\[WARN\]" -or $doctorOutput -match "DEV DOCTOR RESULT:\s+OK WITH WARNINGS") {
    $warnings += 1
}

Write-Host ""
Write-Host "Step 2/3 - Smoke tests" -ForegroundColor Cyan
$smokeScript = Join-Path $projectRoot "scripts\test_smoke.ps1"
& powershell -ExecutionPolicy Bypass -File $smokeScript -StopOnFirstFail
$smokeExitCode = $LASTEXITCODE
if ($smokeExitCode -ne 0) {
    Write-Host ""
    Write-Fail "FINAL RESULT: NO-GO"
    Write-Fail "Reason: smoke tests failed"
    Write-Host "Recommended next action: inspect failing test and rerun smoke suite."
    exit 1
}

Write-Host ""
Write-Host "Step 3/3 - Health check (optional)" -ForegroundColor Cyan
$healthUrl = "http://127.0.0.1:5005/health"
try {
    $response = Invoke-WebRequest -Uri $healthUrl -Method Get -TimeoutSec 4 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Pass "Health check OK ($healthUrl)"
    } else {
        Write-Warn "Health check failed ($healthUrl) - status: $($response.StatusCode)"
        $warnings += 1
    }
} catch {
    $errText = $_.Exception.Message
    if ($errText -match "actively refused" -or $errText -match "Unable to connect" -or $errText -match "No connection could be made") {
        Write-Warn "Health check skipped: local server is not running."
    } else {
        Write-Warn "Health check failed ($healthUrl): $errText"
    }
    $warnings += 1
}

Write-Host ""
if ($warnings -gt 0) {
    Write-Host "FINAL RESULT: GO WITH WARNINGS" -ForegroundColor Yellow
    Write-Host "Recommended next action: review warnings, then proceed with local run/demo carefully."
} else {
    Write-Host "FINAL RESULT: GO" -ForegroundColor Green
    Write-Host "Recommended next action: proceed with local work or demo."
}

exit 0
