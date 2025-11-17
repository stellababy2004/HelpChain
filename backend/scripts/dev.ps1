Param(
    [ValidateSet('run','smoke','health','fts-status','fts-rebuild','reset-db','login')]
    [string]$Task = 'run',
    [string]$BaseUrl = 'http://127.0.0.1:5000',
    [string]$Username = 'admin',
    [string]$Password = 'secret123',
    [switch]$NoLog
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info([string]$Message) {
    Write-Host "[dev] $Message" -ForegroundColor Cyan
}

function Get-BackendRoot {
    if ($PSScriptRoot) {
        return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    }
    elseif ($MyInvocation -and $MyInvocation.MyCommand -and $MyInvocation.MyCommand.Path) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        return (Resolve-Path (Join-Path $scriptDir '..')).Path
    }
    else {
        # Fallback to current directory
        return (Get-Location).Path
    }
}

function Invoke-Health {
    param([string]$Url)
    Write-Info "Health at $Url"
    Invoke-RestMethod "$Url/api/_health" | ConvertTo-Json -Depth 6
}

function Invoke-Login {
    param([string]$Url, [string]$User, [string]$Pass)
    Write-Info "Login $User at $Url"
    $body = @{ username=$User; password=$Pass } | ConvertTo-Json
    $resp = Invoke-RestMethod -Method Post -Uri "$Url/api/login" -Body $body -ContentType 'application/json'
    return $resp.access_token
}

function Invoke-FTSStatus {
    param([string]$Url, [string]$Token)
    $headers = @{ Authorization = "Bearer $Token" }
    Write-Info "FTS status at $Url"
    Invoke-RestMethod -Headers $headers -Uri "$Url/api/_fts_status" | ConvertTo-Json -Depth 6
}

function Invoke-Smoke {
    $root = Get-BackendRoot
    Push-Location $root
    try {
        Write-Info "Running smoke_fts.py"
        python scripts/smoke_fts.py
    } finally {
        Pop-Location
    }
}

function Invoke-Run {
    $root = Get-BackendRoot
    Push-Location $root
    try {
        Write-Info "Starting app.py"
        python app.py
    } finally {
        Pop-Location
    }
}

function Invoke-FTSRebuild {
    $root = Get-BackendRoot
    Push-Location $root
    try {
        Write-Info "Rebuilding FTS index"
        python scripts/fts_rebuild.py
    } finally {
        Pop-Location
    }
}

function Invoke-ResetDb {
    $root = Get-BackendRoot
    $db = Join-Path $root 'instance/volunteers.db'
    if (Test-Path $db) {
        Write-Info "Removing $db"
        Remove-Item $db -Force
    } else {
        Write-Info "No DB file to remove ($db)"
    }
}

# --- Simple transcript logging to ./.logs ---
if (-not $NoLog) {
    try {
        $root = Get-BackendRoot
        $logDir = Join-Path $root '.logs'
        if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
        $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
        $logFile = Join-Path $logDir ("dev-$Task-$ts.log")
        Start-Transcript -Path $logFile -IncludeInvocationHeader -ErrorAction SilentlyContinue | Out-Null
        Write-Info "Logging to $logFile"
    } catch {
        Write-Verbose "Transcript could not start: $($_.Exception.Message)"
    }
}

try {
    switch ($Task) {
        'health'      { Invoke-Health -Url $BaseUrl }
        'login'       { $t = Invoke-Login -Url $BaseUrl -User $Username -Pass $Password; Write-Output $t }
        'fts-status'  { $t = Invoke-Login -Url $BaseUrl -User $Username -Pass $Password; Invoke-FTSStatus -Url $BaseUrl -Token $t }
        'smoke'       { Invoke-Smoke }
        'fts-rebuild' { Invoke-FTSRebuild }
        'reset-db'    { Invoke-ResetDb }
        'run'         { Invoke-Run }
        Default       { throw "Unknown task: $Task" }
    }
}
finally {
    if (-not $NoLog) {
        try { Stop-Transcript -ErrorAction SilentlyContinue | Out-Null } catch {}
    }
}
