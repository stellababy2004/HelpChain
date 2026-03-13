param(
    [ValidateSet("start", "stop", "restart", "status", "logs", "serve")]
    [string]$Action = "serve"
)

$ErrorActionPreference = "Stop"

$Root = "c:\dev\HelpChain.bg"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$RunFile = Join-Path $Root "run.py"
$TmpDir = Join-Path $Root "tmp"
$PidFile = Join-Path $TmpDir "helpchain_server.pid"
$OutLog = Join-Path $TmpDir "server.out.log"
$ErrLog = Join-Path $TmpDir "server.err.log"
$Port = 5000

function Ensure-TmpDir {
    if (!(Test-Path $TmpDir)) {
        New-Item -ItemType Directory -Path $TmpDir | Out-Null
    }
}

function Get-PortPids {
    $lines = netstat -ano | Select-String ":$Port"
    $pids = @()
    foreach ($line in $lines) {
        if ($line -match "LISTENING\s+(\d+)$") {
            $pids += [int]$Matches[1]
        }
    }
    $pids | Select-Object -Unique
}

function Stop-ByPid([int]$TargetPid) {
    try {
        $proc = Get-Process -Id $TargetPid -ErrorAction Stop
        Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 400
        Write-Output "Stopped PID $TargetPid"
    } catch {
        Write-Output "PID $TargetPid already stopped"
    }
}

function Stop-Server {
    if (Test-Path $PidFile) {
        $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        $parsed = $raw -as [int]
        if ($raw -and $parsed -and $parsed -gt 0) {
            Stop-ByPid -TargetPid $parsed
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }

    $portPids = Get-PortPids
    foreach ($portPid in $portPids) {
        Stop-ByPid -TargetPid $portPid
    }
}

function Start-Server {
    Ensure-TmpDir

    if (!(Test-Path $Python)) {
        throw "Python not found: $Python"
    }
    if (!(Test-Path $RunFile)) {
        throw "run.py not found: $RunFile"
    }

    $proc = Start-Process -FilePath $Python `
        -ArgumentList $RunFile `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -PassThru

    Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
    Start-Sleep -Seconds 2

    $livePortPids = Get-PortPids
    if ($livePortPids -contains $proc.Id) {
        Write-Output "Server started. PID=$($proc.Id) URL=http://127.0.0.1:$Port"
        return
    }

    Write-Output "Server process did not bind to port $Port yet. Check logs:"
    Write-Output "OUT: $OutLog"
    Write-Output "ERR: $ErrLog"
}

function Serve-Foreground {
    Ensure-TmpDir
    Stop-Server
    Write-Output "Starting foreground server on http://127.0.0.1:$Port"
    Set-Location $Root
    & $Python $RunFile
}

function Show-Status {
    $trackedPid = $null
    if (Test-Path $PidFile) {
        $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        $parsed = $raw -as [int]
        if ($raw -and $parsed -and $parsed -gt 0) {
            $trackedPid = $parsed
        }
    }
    $portPids = Get-PortPids
    Write-Output "PID file: $PidFile"
    Write-Output ("PID from file: " + ($(if ($trackedPid) { $trackedPid } else { "none" })))
    Write-Output ("PIDs listening on :$Port -> " + ($(if ($portPids) { ($portPids -join ", ") } else { "none" })))
    if ($trackedPid) {
        Get-Process -Id $trackedPid -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime
    }
}

function Show-Logs {
    Ensure-TmpDir
    if (Test-Path $OutLog) { Get-Content $OutLog -Tail 80 }
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 80 }
}

switch ($Action) {
    "start" { Start-Server }
    "stop" { Stop-Server }
    "restart" { Stop-Server; Start-Server }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "serve" { Serve-Foreground }
}
