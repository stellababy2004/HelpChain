param(
    [switch]$UseAltDeps,
    [string]$PythonExe = "python",
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 5000,
    [switch]$SkipInstall,
    [switch]$JustInstall,
    [switch]$UpdateDeps,
    [switch]$SyncDeps
)

$ErrorActionPreference = "Stop"

Write-Host "[HelpChain] Starting setup script..." -ForegroundColor Cyan

# Resolve project root (backend folder where script lives two levels up)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Split-Path -Parent $ScriptDir
Set-Location $BackendDir

$venvPath = Join-Path $BackendDir ".venv"
$requirementsFile = if ($UseAltDeps) { "requirements-alt.txt" } else { "requirements.txt" }

if (-not (Test-Path $requirementsFile)) {
    Write-Host "Requirements file not found: $requirementsFile" -ForegroundColor Red
    exit 1
}

function New-Venv {
    if (-not (Test-Path $venvPath)) {
        Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
        & $PythonExe -m venv $venvPath
    } else {
        Write-Host "Virtual environment already exists." -ForegroundColor DarkGray
    }
}

function Enable-Venv {
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        Write-Host "Activate script missing; recreate venv." -ForegroundColor Red
        Remove-Item -Recurse -Force $venvPath
        New-Venv
    }
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    . $activateScript
}

function Install-Dependencies {
    Write-Host "Installing dependencies from $requirementsFile..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install -r $requirementsFile
}

function Update-DependenciesWithPipTools {
    Write-Host "Updating pinned dependencies via pip-tools..." -ForegroundColor Yellow
    pip install --upgrade pip-tools
    if (-not (Test-Path "requirements.in")) {
        Write-Host "requirements.in missing -> creating a minimal base file." -ForegroundColor DarkYellow
        @'
# Auto-generated minimal requirements.in
Flask
Flask-SQLAlchemy
Flask-Migrate
Flask-Mail
Flask-Babel
Flask-Login
Flask-SocketIO
celery
redis
psycopg2-binary
httpx
numpy
pandas
scikit-learn
pytest
sentry-sdk[flask]
'@ | Set-Content requirements.in
    }
    pip-compile requirements.in --output-file requirements.txt
    if ($SyncDeps) {
        Write-Host "Syncing environment strictly to compiled requirements.txt" -ForegroundColor Yellow
        pip-sync requirements.txt
    } else {
        Write-Host "Install compiled requirements.txt (non-strict)" -ForegroundColor Yellow
        pip install -r requirements.txt
    }
}

function Start-App {
    Write-Host "Starting Flask app (host=$ListenHost port=$Port)..." -ForegroundColor Green
    $env:FLASK_APP = "app.py"
    $env:FLASK_RUN_HOST = $ListenHost
    $env:FLASK_RUN_PORT = $Port
    python app.py
}

New-Venv
Enable-Venv

if (-not $SkipInstall) {
    Install-Dependencies
} else {
    Write-Host "--SkipInstall specified: skipping dependency install." -ForegroundColor DarkYellow
}

if ($UpdateDeps) {
    Update-DependenciesWithPipTools
    if ($JustInstall) {
        Write-Host "Dependencies updated and JustInstall specified; exiting." -ForegroundColor Cyan
        exit 0
    }
}

if ($JustInstall) {
    Write-Host "JustInstall flag set; exiting after installation." -ForegroundColor Cyan
    exit 0
}

Start-App
