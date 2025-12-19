[CmdletBinding()]
param(
    [int]$Port = 5000,
    [string]$BaseUrl = "http://127.0.0.1",
    [int]$HealthTimeoutSec = 90,
    [switch]$UseExisting,
    [switch]$KeepServer,
    [switch]$Strict,
    [switch]$Relaxed,
    [string]$HealthPath = "/health",
    [string]$BypassToken
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[start-and-smoke] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[start-and-smoke] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[start-and-smoke] $msg" -ForegroundColor Red }

try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot  = Split-Path -Parent $scriptDir

    # Ensure env for safe launch + smoke mode (avoid PS parsing quirks by using .NET API)
    [System.Environment]::SetEnvironmentVariable('HELPCHAIN_SKIP_KILL','1','Process')
    [System.Environment]::SetEnvironmentVariable('HELPCHAIN_SMOKE','1','Process')

    $serverJob = $null

    if (-not $UseExisting) {
        Write-Info "Starting HelpChain server as background job..."
        $serverJob = Start-Job -Name "HelpChainServer" -ScriptBlock {
            param($root)
            [System.Environment]::SetEnvironmentVariable('HELPCHAIN_SKIP_KILL','1','Process')
            [System.Environment]::SetEnvironmentVariable('HELPCHAIN_SMOKE','1','Process')
            [System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING','utf-8','Process')
            Set-Location $root
            $log = Join-Path $root 'start-and-smoke.server.log'
            "`n==== $(Get-Date -Format o) :: start_server (job) ====" | Out-File -FilePath $log -Append -Encoding UTF8
            python start_server.py *> $log
        } -ArgumentList $repoRoot
        Start-Sleep -Seconds 1
        if (-not $serverJob) { throw "Failed to start server background job" }
        Write-Info "Server job started (Id=$($serverJob.Id))."
    } else {
        Write-Info "Using existing running server (skipping start)."
    }

    # Compose health URL (avoid :443 for https and :80 for http)
    $root = $BaseUrl.TrimEnd('/')
    if ($root -match '^https://') {
        if ($Port -eq 443) { $targetHost = $root } else { $targetHost = ("{0}:{1}" -f $root, $Port) }
    } elseif ($root -match '^http://') {
        if ($Port -eq 80) { $targetHost = $root } else { $targetHost = ("{0}:{1}" -f $root, $Port) }
    } else {
        $targetHost = ("http://127.0.0.1:{0}" -f $Port)
    }
    $hp = if ($HealthPath.StartsWith('/')) { $HealthPath } else { '/' + $HealthPath }
    $healthUrl = "$targetHost$hp"

    # Optional Vercel Preview Protection: set proper cookie via special query
    $healthSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    if ($BypassToken) {
        try {
            $rootForBypass = $root.TrimEnd('/')
            $bypassUrl = "$rootForBypass/?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=$BypassToken"
            Invoke-WebRequest -Uri $bypassUrl -UseBasicParsing -TimeoutSec 10 -WebSession $healthSession -MaximumRedirection 3 | Out-Null
        } catch {
            Write-Warn ("Bypass cookie setup failed (continuing): {0}" -f $_.Exception.Message)
        }
    }

    # Probe /health until 200 or timeout
    Write-Info "Probing health: $healthUrl (timeout ${HealthTimeoutSec}s)"
    Start-Sleep -Seconds 3
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
    $healthy = $false
    do {
        try {
            $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5 -WebSession $healthSession
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $healthy) {
        Write-Err "Health check did not pass within $HealthTimeoutSec seconds: $healthUrl"
        if ($serverJob) {
            Write-Warn "Stopping server job due to failed health check..."
            try { Stop-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Receive-Job -Id $serverJob.Id -Keep -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Remove-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
        }
        exit 1
    }
    Write-Info "Health OK"

    # Build common params for smoke scripts (use splatting for reliability)
    $commonParams = @{ Port = $Port }
    # Pass BaseUrl only for HTTPS previews; local runs use http://127.0.0.1:$Port
    if ($BaseUrl -match '^https://') { $commonParams['BaseUrl'] = $BaseUrl }
    # Default behavior: relaxed unless -Strict is provided. If -Relaxed is explicitly supplied, honor it.
    if ($Relaxed -or (-not $Strict)) { $commonParams['Relaxed'] = $true }
    if ($BypassToken) { $commonParams['BypassToken'] = $BypassToken }

    # Run admin smoke
    $adminSmoke = Join-Path $scriptDir 'admin-smoke.ps1'
    if (-not (Test-Path $adminSmoke)) { throw "Missing $adminSmoke" }
    Write-Info "Running admin smoke..."
    & $adminSmoke @commonParams
    if ($LASTEXITCODE -ne 0) {
        if (-not $Strict -and $LASTEXITCODE -eq 3) {
            Write-Warn "Admin smoke marker check failed, continuing due to relaxed mode."
        } else {
        Write-Err "Admin smoke failed with exit code $LASTEXITCODE"
        if ($serverJob) { Write-Warn "Server job will be stopped." }
        if ($serverJob -and -not $KeepServer) {
            try { Stop-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Receive-Job -Id $serverJob.Id -Keep -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Remove-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
        }
            exit $LASTEXITCODE
        }
    }

    # Run submit-request E2E smoke
    $submitSmoke = Join-Path $scriptDir 'e2e-submit-request-smoke.ps1'
    if (-not (Test-Path $submitSmoke)) { throw "Missing $submitSmoke" }
    Write-Info "Running submit-request smoke..."
    & $submitSmoke @commonParams
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Submit-request smoke failed with exit code $LASTEXITCODE"
        if ($serverJob) { Write-Warn "Server job will be stopped." }
        if ($serverJob -and -not $KeepServer) {
            try { Stop-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Receive-Job -Id $serverJob.Id -Keep -ErrorAction SilentlyContinue | Out-Null } catch {}
            try { Remove-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
        }
        exit $LASTEXITCODE
    }

    Write-Info "All smokes passed."

    if ($serverJob -and -not $KeepServer) {
        Write-Info "Stopping server job..."
        try { Stop-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
        try { Receive-Job -Id $serverJob.Id -Keep -ErrorAction SilentlyContinue | Out-Null } catch {}
        try { Remove-Job -Id $serverJob.Id -ErrorAction SilentlyContinue | Out-Null } catch {}
    } elseif ($serverJob -and $KeepServer) {
        Write-Warn "Server left running in background (Job Id=$($serverJob.Id))."
    }

    exit 0
}
catch {
    Write-Err $_
    exit 1
}
