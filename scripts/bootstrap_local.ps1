Write-Host ""
Write-Host "========================================="
Write-Host "HelpChain Local Bootstrap"
Write-Host "========================================="
Write-Host ""

$ErrorActionPreference = "Stop"

$PY = ".\.venv\Scripts\python.exe"

Write-Host "STEP 1 — Running migrations"
& $PY -m flask db upgrade

Write-Host ""
Write-Host "STEP 2 — Bootstrapping missing schema"
& $PY .\backend\scripts\bootstrap_schema.py --confirm-canonical-db

Write-Host ""
Write-Host "STEP 3 — Creating / resetting admin"

if (-not $env:ADMIN_PASSWORD) {
    $env:ADMIN_PASSWORD = "Admin123!ChangeMe"
}

& $PY .\scripts\reset_admin_local.py --confirm-canonical-db

Write-Host ""
Write-Host "STEP 4 — Running doctor diagnostics"
powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1

Write-Host ""
Write-Host "========================================="
Write-Host "Bootstrap complete"
Write-Host "========================================="
Write-Host ""
