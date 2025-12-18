param(
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$SkipVenv,
  [switch]$NoStart,
  [switch]$ResetDb,
  [switch]$Block,
  [int]$Port = 5000,
  [switch]$RunAdminSmoke,
  [switch]$RunSubmitSmoke
)

Write-Host "=== HelpChain Ops Bootstrap ===" -ForegroundColor Cyan

$ErrorActionPreference = 'Stop'

function Resolve-Python {
  if (-not $SkipVenv) {
    if (-not (Test-Path ".venv")) {
      Write-Host "[1/5] Creating virtualenv (.venv)" -ForegroundColor Yellow
      python -m venv .venv
    }
    $venvPy = Join-Path ".venv" "Scripts/python.exe"
    if (Test-Path $venvPy) { return $venvPy }
  }
  return "python"
}

try {
  Write-Host "[0/5] Checking Python..." -ForegroundColor Yellow
  python --version | Out-Host
} catch {
  Write-Error "Python is not available on PATH. Install Python 3.11+ and retry."
  exit 1
}

$py = Resolve-Python

if (-not $DatabaseUrl) {
  $DatabaseUrl = "sqlite:///backend/instance/volunteers.db"
}
$env:DATABASE_URL = $DatabaseUrl

Write-Host "[2/5] Installing dependencies" -ForegroundColor Yellow
& $py -m pip install --upgrade pip | Out-Host
& $py -m pip install -r requirements.txt | Out-Host

Write-Host "[3/5] Running Alembic migrations" -ForegroundColor Yellow
try {
  $migOut = & $py run_migrations.py *>&1
  $migCode = $LASTEXITCODE
} catch {
  $migOut = $_ | Out-String
  $migCode = 1
}
$migOut | Out-Host

if ($migCode -ne 0) {
  if ($migOut -match "database disk image is malformed") {
    $dbPath = $DatabaseUrl -replace "^sqlite:///", ""
    if (-not [System.IO.Path]::IsPathRooted($dbPath)) {
      $dbPath = Join-Path (Get-Location) $dbPath
    }
    if ($ResetDb) {
      Write-Warning "Alembic failed: malformed DB. Resetting at $dbPath and retrying..."
      try {
        if (Test-Path $dbPath) { Remove-Item -Force -ErrorAction Stop $dbPath }
      } catch { Write-Warning ("Could not remove {0}: {1}" -f $dbPath, $_) }
      $migOut = & $py run_migrations.py 2>&1
      $migCode = $LASTEXITCODE
      $migOut | Out-Host
    } else {
      Write-Warning "Alembic failed due to malformed SQLite file. Re-run with -ResetDb to recreate the DB."
    }
  }
}

Write-Host "[4/5] Quick health check" -ForegroundColor Yellow
& $py -c "import sys; import backend.appy as appy; app = appy.app; print('App loaded; routes:', len(app.url_map._rules))" | Out-Host

if ($NoStart) {
  Write-Host "[5/5] Skipping server start (NoStart set)." -ForegroundColor Yellow
  Write-Host "Run to start:" -ForegroundColor DarkYellow
  Write-Host ("  {0} start_server.py`n" -f $py)
  exit 0
}

Write-Host "[5/5] Starting server on port $Port" -ForegroundColor Yellow
$env:PORT = "$Port"
# Configure env in current session (for foreground) and pass into background job explicitly
$smokeEnabled = [bool]($RunAdminSmoke -or $RunSubmitSmoke)
if ($smokeEnabled) { $env:HELPCHAIN_SMOKE = "1" }
$env:HELPCHAIN_SKIP_KILL = "1"

if ($Block) {
  # Preserve legacy behavior: start in foreground and block
  & $py start_server.py
  exit $LASTEXITCODE
}

# Start the server in background and run a quick health smoke
$job = Start-Job -ScriptBlock {
  param($py, $smoke)
  # Re-apply env vars inside the job's PowerShell process
  $env:HELPCHAIN_SKIP_KILL = "1"
  if ($smoke) { $env:HELPCHAIN_SMOKE = "1" }
  $env:PORT = $env:PORT
  & $py start_server.py
} -ArgumentList $py, $smokeEnabled

Write-Host "Server starting in background (Job Id: $($job.Id)). Running health check..." -ForegroundColor Yellow

$healthUrl = "http://127.0.0.1:$Port/health"
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
      $ok = $true
      break
    }
  } catch {
    # keep waiting
  }
}

if ($ok) {
  Write-Host "Health OK at $healthUrl" -ForegroundColor Green
  Write-Host "Open: http://127.0.0.1:$Port/" -ForegroundColor Green
  # Optionally run smoke checks
  if ($RunAdminSmoke) {
    Write-Host "Running admin smoke..." -ForegroundColor Yellow
    try {
      pwsh -File (Join-Path (Get-Location) "scripts/admin-smoke.ps1") -Port $Port | Out-Host
    } catch { Write-Warning ("Admin smoke failed: {0}" -f $_.Exception.Message) }
  }
  if ($RunSubmitSmoke) {
    Write-Host "Running E2E submit-request smoke..." -ForegroundColor Yellow
    try {
      pwsh -File (Join-Path (Get-Location) "scripts/e2e-submit-request-smoke.ps1") -Port $Port | Out-Host
    } catch { Write-Warning ("Submit smoke failed: {0}" -f $_.Exception.Message) }
  }
} else {
  Write-Warning "Health check did not pass within timeout. Check logs (Receive-Job -Id $($job.Id) -Keep)."
}

Write-Host "Server is running in background. To stop: Stop-Job -Id $($job.Id) ; Receive-Job -Id $($job.Id)" -ForegroundColor DarkYellow
