[CmdletBinding()]
param(
    [string[]]$GateLangs = @('bg', 'en', 'fr', 'es', 'de', 'it'),
    [string[]]$TemplateGateLangs = @('bg'),
    [string[]]$PipelineLangs = @('bg'),
    [string[]]$SourceLocales = @('en', 'fr'),
    [switch]$SkipPipeline,
    [switch]$ContinueOnError,
    [switch]$OverwriteIdenticalOnly,
    [int]$MaxMessages = 0,
    [switch]$ShowAllQuality,
    [switch]$StrictQualityAll
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[i18n-ci-smoke] $msg" -ForegroundColor Cyan }
function Write-WarnMsg($msg) { Write-Host "[i18n-ci-smoke] $msg" -ForegroundColor Yellow }
function Write-ErrMsg($msg)  { Write-Host "[i18n-ci-smoke] $msg" -ForegroundColor Red }
function Expand-List([string[]]$Items) {
    $out = @()
    foreach ($item in ($Items | Where-Object { $_ -ne $null })) {
        foreach ($part in ($item -split ',')) {
            $v = $part.Trim()
            if ($v) { $out += $v }
        }
    }
    return ,$out
}

try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot  = Split-Path -Parent $scriptDir
    Set-Location $repoRoot

    $py = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $py = "python"
    }

    [System.Environment]::SetEnvironmentVariable('PYTHONUTF8','1','Process')

    $GateLangs = Expand-List $GateLangs
    $TemplateGateLangs = Expand-List $TemplateGateLangs
    $PipelineLangs = Expand-List $PipelineLangs
    $SourceLocales = Expand-List $SourceLocales
    $warningOnlyQualityLangs = @()
    if (-not $StrictQualityAll) {
        $templateGateSet = @{}
        foreach ($l in $TemplateGateLangs) { $templateGateSet[$l] = $true }
        foreach ($l in $GateLangs) {
            if (-not $templateGateSet.ContainsKey($l)) { $warningOnlyQualityLangs += $l }
        }
    }

    Write-Info "Repo root: $repoRoot"
    Write-Info "Python: $py"

    foreach ($gateLang in $TemplateGateLangs) {
        $cmd = @($py, "scripts/i18n_template_smoke.py")
        if ($SkipPipeline) {
            $cmd += "--skip-pipeline"
        } else {
            $cmd += @("--langs") + $PipelineLangs
            $cmd += @("--source-locales") + $SourceLocales
            if ($ContinueOnError) { $cmd += "--continue-on-error" }
            if ($OverwriteIdenticalOnly) { $cmd += "--overwrite-identical-only" }
            if ($MaxMessages -gt 0) { $cmd += @("--max-messages", "$MaxMessages") }
        }
        $cmd += @("--gate-lang", $gateLang)

        Write-Info ("Template smoke ({0})..." -f $gateLang)
        & $cmd[0] $cmd[1..($cmd.Length-1)]
        if ($LASTEXITCODE -ne 0) {
            throw "Template smoke failed for gate_lang=$gateLang (exit=$LASTEXITCODE)"
        }
    }

    $qcmd = @($py, "scripts/i18n_quality_smoke.py")
    if ($GateLangs -and $GateLangs.Count -gt 0) {
        $qcmd += @("--langs") + $GateLangs
    }
    if ($warningOnlyQualityLangs.Count -gt 0) {
        $qcmd += @("--warning-only-langs") + $warningOnlyQualityLangs
        Write-WarnMsg ("Quality warning-only locales: {0}" -f (($warningOnlyQualityLangs -join ", ")))
    }
    if ($ShowAllQuality) {
        $qcmd += "--show-all"
    }

    Write-Info ("Quality smoke ({0})..." -f (($GateLangs -join ", ")))
    & $qcmd[0] $qcmd[1..($qcmd.Length-1)]
    if ($LASTEXITCODE -ne 0) {
        throw "Quality smoke failed (exit=$LASTEXITCODE)"
    }

    Write-Info "All i18n smokes passed."
    exit 0
}
catch {
    Write-ErrMsg $_
    exit 1
}
