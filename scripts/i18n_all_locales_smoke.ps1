[CmdletBinding()]
param(
    [switch]$SkipPipeline,
    [switch]$ContinueOnError,
    [switch]$ContinueThroughFailures,
    [switch]$OverwriteIdenticalOnly,
    [int]$MaxMessages = 0,
    [string[]]$SourceLocales = @('en', 'fr'),
    [ValidateSet('core','extended')]
    [string]$TemplateProfile = 'core',
    [switch]$ShowAllQuality,
    [string[]]$RequiredLocales = @(),
    [string[]]$WarningOnlyLocales = @()
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[i18n-all-locales] $msg" -ForegroundColor Cyan }
function Write-ErrMsg($msg) { Write-Host "[i18n-all-locales] $msg" -ForegroundColor Red }
function Write-WarnMsg($msg) { Write-Host "[i18n-all-locales] $msg" -ForegroundColor Yellow }
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
    $repoRoot = Split-Path -Parent $scriptDir
    Set-Location $repoRoot

    $py = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }

    [System.Environment]::SetEnvironmentVariable('PYTHONUTF8','1','Process')
    $RequiredLocales = Expand-List $RequiredLocales
    $WarningOnlyLocales = Expand-List $WarningOnlyLocales

    Write-Info "Reading locale codes from templates/base.html ..."
    $codes = & $py scripts/i18n_accessibility_locales.py --format lines
    if ($LASTEXITCODE -ne 0) { throw "Failed to extract locale codes from templates/base.html" }
    $localeList = @($codes | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
    if (-not $localeList -or $localeList.Count -eq 0) { throw "No locales found in accessibility menu." }
    Write-Info ("Locales ({0}): {1}" -f $localeList.Count, ($localeList -join ", "))
    $templateFailures = @()
    $templateWarnings = @()
    $qualityFailed = $false
    $requiredSet = @{}
    $warningOnlySet = @{}
    foreach ($l in $RequiredLocales) { $requiredSet[$l] = $true }
    foreach ($l in $WarningOnlyLocales) { $warningOnlySet[$l] = $true }

    if ($RequiredLocales.Count -gt 0) {
        # If required locales are provided, all non-required locales default to warning-only.
        foreach ($l in $localeList) {
            if (-not $requiredSet.ContainsKey($l)) { $warningOnlySet[$l] = $true }
        }
        Write-Info ("Required locales (hard fail): {0}" -f (($RequiredLocales -join ", ")))
    } elseif ($WarningOnlyLocales.Count -gt 0) {
        Write-Info ("Warning-only locales: {0}" -f (($WarningOnlyLocales -join ", ")))
    }

    # Run template smoke per locale (optionally with refresh pipeline)
    foreach ($lang in $localeList) {
        $cmd = @($py, "scripts/i18n_template_smoke.py", "--gate-lang", $lang, "--template-profile", $TemplateProfile)
        if ($SkipPipeline) {
            $cmd += "--skip-pipeline"
        } else {
            $cmd += @("--langs", $lang)
            $cmd += @("--source-locales") + $SourceLocales
            if ($ContinueOnError) { $cmd += "--continue-on-error" }
            if ($OverwriteIdenticalOnly) { $cmd += "--overwrite-identical-only" }
            if ($MaxMessages -gt 0) { $cmd += @("--max-messages", "$MaxMessages") }
        }
        Write-Info ("Template smoke [{0}] ({1})" -f $lang, $TemplateProfile)
        & $cmd[0] $cmd[1..($cmd.Length-1)]
        if ($LASTEXITCODE -ne 0) {
            $isWarningOnly = $warningOnlySet.ContainsKey($lang)
            if ($ContinueThroughFailures) {
                if ($isWarningOnly) {
                    $templateWarnings += [PSCustomObject]@{ Locale = $lang; ExitCode = $LASTEXITCODE }
                    Write-WarnMsg ("Template smoke warning-only failure for locale={0} (exit={1}); continuing..." -f $lang, $LASTEXITCODE)
                } else {
                    $templateFailures += [PSCustomObject]@{ Locale = $lang; ExitCode = $LASTEXITCODE }
                    Write-WarnMsg ("Template smoke failed for locale={0} (exit={1}); continuing..." -f $lang, $LASTEXITCODE)
                }
                continue
            }
            if ($isWarningOnly) {
                $templateWarnings += [PSCustomObject]@{ Locale = $lang; ExitCode = $LASTEXITCODE }
                Write-WarnMsg ("Template smoke warning-only failure for locale={0} (exit={1}); continuing..." -f $lang, $LASTEXITCODE)
                continue
            }
            throw "Template smoke failed for locale=$lang (exit=$LASTEXITCODE)"
        }
    }

    # Run quality smoke for all locales (heuristics for all; exact checks for configured locales)
    $qcmd = @($py, "scripts/i18n_quality_smoke.py", "--template-profile", $TemplateProfile, "--langs") + $localeList
    if ($warningOnlySet.Count -gt 0) {
        $qWarning = @($warningOnlySet.Keys | Sort-Object)
        if ($qWarning.Count -gt 0) { $qcmd += @("--warning-only-langs") + $qWarning }
    }
    if ($ShowAllQuality) { $qcmd += "--show-all" }
    Write-Info ("Quality smoke all locales ({0})" -f $TemplateProfile)
    & $qcmd[0] $qcmd[1..($qcmd.Length-1)]
    if ($LASTEXITCODE -ne 0) {
        if ($ContinueThroughFailures) {
            $qualityFailed = $true
            Write-WarnMsg ("Quality smoke failed (exit={0})" -f $LASTEXITCODE)
        } else {
            throw "Quality smoke failed (exit=$LASTEXITCODE)"
        }
    }

    if ($templateFailures.Count -gt 0 -or $qualityFailed) {
        Write-ErrMsg "Summary: i18n all-locales smoke completed with failures."
        if ($templateFailures.Count -gt 0) {
            Write-Host "[i18n-all-locales] Template smoke failures by locale:" -ForegroundColor Yellow
            foreach ($f in $templateFailures) {
                Write-Host ("- {0} (exit={1})" -f $f.Locale, $f.ExitCode) -ForegroundColor Yellow
            }
        }
        if ($qualityFailed) {
            Write-Host "[i18n-all-locales] Quality smoke: FAILED" -ForegroundColor Yellow
        } else {
            Write-Host "[i18n-all-locales] Quality smoke: PASS" -ForegroundColor Green
        }
        if ($templateWarnings.Count -gt 0) {
            Write-Host "[i18n-all-locales] Template smoke warning-only failures by locale:" -ForegroundColor Yellow
            foreach ($f in $templateWarnings) {
                Write-Host ("- {0} (exit={1})" -f $f.Locale, $f.ExitCode) -ForegroundColor Yellow
            }
        }
        exit 1
    }

    if ($templateWarnings.Count -gt 0) {
        Write-WarnMsg "Summary: completed with warning-only template failures."
        Write-Host "[i18n-all-locales] Template smoke warning-only failures by locale:" -ForegroundColor Yellow
        foreach ($f in $templateWarnings) {
            Write-Host ("- {0} (exit={1})" -f $f.Locale, $f.ExitCode) -ForegroundColor Yellow
        }
    }

    Write-Info "All locale smokes passed."
    exit 0
}
catch {
    Write-ErrMsg $_
    exit 1
}
