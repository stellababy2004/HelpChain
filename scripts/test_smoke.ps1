param(
    [switch]$CollectOnly,
    [switch]$Verbose,
    [switch]$StopOnFirstFail
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python executable not found at $pythonExe" -ForegroundColor Red
    Write-Host "Create/activate .venv first, then retry." -ForegroundColor Red
    exit 1
}

$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) "HelpChainSmoke"
if (-not (Test-Path $tmpRoot)) {
    New-Item -ItemType Directory -Path $tmpRoot | Out-Null
}
$runStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$smokeDbPath = Join-Path $tmpRoot ("smoke_pytest_{0}.sqlite" -f $runStamp)
$env:HC_ENV = "test"
$env:HELPCHAIN_TESTING = "1"
$env:HC_DB_PATH = $smokeDbPath
$env:TMPDIR = $tmpRoot
$env:TEMP = $tmpRoot
$env:TMP = $tmpRoot
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:SQLALCHEMY_DATABASE_URI -ErrorAction SilentlyContinue

$tests = @(
    "tests\test_request_details_workspace.py",
    "tests\test_admin_request_new_smoke.py",
    "tests\test_admin_pilotage_tendances_observees_smoke.py"
)

$pytestArgs = @("-m", "pytest")
if ($CollectOnly) {
    $pytestArgs += @("--collect-only", "-q")
} elseif ($Verbose) {
    $pytestArgs += @("-vv", "-s")
} else {
    $pytestArgs += @("-q")
}
if ($StopOnFirstFail) {
    $pytestArgs += @("-x")
}
$pytestArgs += $tests

Write-Host ""
Write-Host "Running HelpChain smoke tests..." -ForegroundColor Cyan
Write-Host "Python: $pythonExe"
Write-Host "Mode: $(if ($CollectOnly) { 'collect-only' } elseif ($Verbose) { 'verbose' } else { 'standard' })"
Write-Host "Stop on first fail: $(if ($StopOnFirstFail) { 'yes' } else { 'no' })"
Write-Host "Isolated test DB: $smokeDbPath"
Write-Host "Test targets:"
foreach ($t in $tests) {
    Write-Host " - $t"
}
Write-Host ""

& $pythonExe @pytestArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "PASS: smoke suite completed successfully." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "FAIL: smoke suite failed (exit code: $exitCode)." -ForegroundColor Red
exit $exitCode
