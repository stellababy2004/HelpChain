param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host ""
    Write-Host "HelpChain Dev Commands"
    Write-Host "----------------------"
    Write-Host "bootstrap       Setup local DB, schema, admin and doctor checks"
    Write-Host "run             Start local server"
    Write-Host "doctor          Run environment diagnostics"
    Write-Host "smoke           Run smoke tests"
    Write-Host "smoke-verbose   Run smoke tests (verbose)"
    Write-Host "smoke-collect   List smoke tests without running"
    Write-Host "go-no-go        Run full readiness check"
    Write-Host "scan-secrets    Scan repo for possible credentials"
    Write-Host "reset-admin     Reset local admin (requires ADMIN_PASSWORD env var)"
    Write-Host "help            Show this help"
    Write-Host ""
}

switch ($Command) {

    "help" {
        Show-Help
    }

    "bootstrap" {
        powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
    }

    "run" {
        powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
    }

    "doctor" {
        powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1
    }

    "doctor-deep" {
        .\.venv\Scripts\python.exe .\scripts\helpchain_doctor.py
    }

    "smoke" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1
    }

    "smoke-verbose" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1 -Verbose
    }

    "smoke-collect" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1 -CollectOnly
    }

    "go-no-go" {
        powershell -ExecutionPolicy Bypass -File .\scripts\go_no_go.ps1
    }

    "scan-secrets" {
        powershell -ExecutionPolicy Bypass -File .\scripts\scan_secrets.ps1
    }

    "reset-admin" {

        if (-not $env:ADMIN_PASSWORD) {
            Write-Host ""
            Write-Host "ERROR: ADMIN_PASSWORD env variable not set."
            Write-Host "Example:"
            Write-Host '$env:ADMIN_PASSWORD="NewStrongPassword!"'
            Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 reset-admin"
            Write-Host ""
            exit 1
        }

        .\.venv\Scripts\python.exe .\scripts\reset_admin_local.py --confirm-canonical-db
    }

    default {
        Write-Host ""
        Write-Host "Unknown command: $Command"
        Show-Help
        exit 1
    }
}
