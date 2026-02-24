Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $repoRoot "run_dev.ps1"

if (-not (Test-Path $target)) {
    throw "Missing target script: $target"
}

& $target
