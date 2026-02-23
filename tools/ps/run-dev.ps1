Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$target = Join-Path $repoRoot "run_dev.ps1"

if (-not (Test-Path $target)) {
    throw "Missing target script: $target"
}

& $target
