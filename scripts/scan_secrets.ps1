[CmdletBinding()]
param(
    [switch]$StagedOnly
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Get-ScanFiles {
    param([bool]$Staged)
    if ($Staged) {
        $files = git diff --cached --name-only --diff-filter=ACMRTUXB 2>$null
    } else {
        $files = git ls-files 2>$null
    }
    if (-not $files) {
        return @()
    }
    return @($files | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Is-IgnoredPath {
    param([string]$PathText)
    return $PathText -match '^(?:\.git/|\.venv/|node_modules/|vendor/|_vendor/|artifacts/|backend/backups/|.*\.backup_.*)'
}

function Is-BinaryFile {
    param([byte[]]$Bytes)
    if (-not $Bytes -or $Bytes.Length -eq 0) { return $false }
    $probeLen = [Math]::Min($Bytes.Length, 4096)
    for ($i = 0; $i -lt $probeLen; $i++) {
        if ($Bytes[$i] -eq 0) { return $true }
    }
    return $false
}

function Is-PlaceholderValue {
    param([string]$Value)
    if ($null -eq $Value) {
        $v = ""
    } else {
        $v = $Value.Trim().ToLowerInvariant()
    }
    if ([string]::IsNullOrWhiteSpace($v)) { return $true }
    if ($v -match 'your_password_here|example|changeme|dummy|placeholder|replace_me|replace-this|sample|fake|test-only|test_secret|dev-only') { return $true }
    if ($v -match '^\*+$|^x+$') { return $true }
    if ($v -match '^\$\{\{?\s*secrets\.' ) { return $true }
    return $false
}

$patterns = @(
    @{ Name = "Hardcoded credential assignment"; Regex = '(?i)\b(?:ADMIN_PASSWORD|PASSWORD|SECRET_KEY|API_KEY|ACCESS_KEY|AWS_SECRET_ACCESS_KEY)\b\s*[:=]\s*["'']([^"'']{6,})["'']' },
    @{ Name = "ENV-like credential assignment"; Regex = '(?i)^\s*(?:ADMIN_PASSWORD|PASSWORD|SECRET_KEY|API_KEY|ACCESS_KEY|AWS_SECRET_ACCESS_KEY)\s*=\s*([^\s#"''][^\s#]{5,})' },
    @{ Name = "Bearer-like token"; Regex = '(?i)\bbearer\s+([A-Za-z0-9\-\._~\+\/=]{20,})' },
    @{ Name = "Token assignment"; Regex = '(?i)\b(?:token|access_token|refresh_token|bearer_token)\b\s*[:=]\s*["'']([A-Za-z0-9\-\._=]{16,})["'']' },
    @{ Name = "Email+password inline"; Regex = '(?i)(?:"email"\s*:\s*"[^"]+"\s*,\s*"password"\s*:\s*"([^"]{6,})")|(?:"password"\s*:\s*"([^"]{6,})"\s*,\s*"email"\s*:\s*"[^"]+")' },
    @{ Name = "AWS secret access key value"; Regex = '(?i)\bAWS_SECRET_ACCESS_KEY\b\s*[:=]\s*["'']?([A-Za-z0-9\/+=]{30,})["'']?' }
)

$files = Get-ScanFiles -Staged:$StagedOnly
if ($files.Count -eq 0) {
    Write-Host "SECRET GUARD: no files to scan."
    exit 0
}

$findings = New-Object System.Collections.Generic.List[object]

foreach ($relPath in $files) {
    $pathNorm = $relPath -replace '\\','/'
    if (Is-IgnoredPath -PathText $pathNorm) { continue }
    if (-not (Test-Path $relPath -PathType Leaf)) { continue }

    try {
        $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $relPath))
    } catch {
        continue
    }
    if (Is-BinaryFile -Bytes $bytes) { continue }

    try {
        $content = [System.IO.File]::ReadAllText((Resolve-Path $relPath))
    } catch {
        continue
    }

    $lines = $content -split "`r?`n"
    for ($lineNo = 0; $lineNo -lt $lines.Length; $lineNo++) {
        $line = $lines[$lineNo]
        foreach ($p in $patterns) {
            $m = [regex]::Match($line, $p.Regex)
            if (-not $m.Success) { continue }

            $secretValue = ""
            for ($gi = 1; $gi -lt $m.Groups.Count; $gi++) {
                if ($m.Groups[$gi].Success -and -not [string]::IsNullOrWhiteSpace($m.Groups[$gi].Value)) {
                    $secretValue = $m.Groups[$gi].Value
                    break
                }
            }
            if (Is-PlaceholderValue -Value $secretValue) { continue }

            $findings.Add([pscustomobject]@{
                File = $relPath
                Line = $lineNo + 1
                Rule = $p.Name
                Snippet = ($line.Trim())
            })
        }
    }
}

if ($findings.Count -gt 0) {
    Write-Host ""
    Write-Host "SECRET GUARD: possible credential detected in staged files." -ForegroundColor Red
    Write-Host "Remove the secret or move it to environment variables before commit." -ForegroundColor Red
    Write-Host ""
    foreach ($f in $findings) {
        Write-Host (" - {0}:{1} [{2}]" -f $f.File, $f.Line, $f.Rule) -ForegroundColor Yellow
    }
    Write-Host ""
    exit 1
}

Write-Host "SECRET GUARD: no obvious credentials detected." -ForegroundColor Green
exit 0
