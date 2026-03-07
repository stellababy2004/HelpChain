Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

$repo = "C:\dev\HelpChain.bg"
$python = Join-Path $repo ".venv\Scripts\python.exe"
$dbPath = "C:\dev\HelpChain.bg\backend\instance\app_clean.db"
$dbUri = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
$port = 5000
$healthUrl = "http://127.0.0.1:5000/admin/ops/login"
$logDir = Join-Path $repo "tmp"
$logFile = Join-Path $logDir "watchdog5000.log"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

function Write-Log([string]$msg) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $logFile -Value $line
}

Write-Log "watchdog start"

while ($true) {
    $listening = $false
    try {
        $lines = netstat -ano | Select-String ":$port"
        if ($lines) {
            foreach ($line in $lines) {
                if ($line.ToString() -match "LISTENING") {
                    $listening = $true
                    break
                }
            }
        }
    } catch {}

    if (-not $listening) {
        try {
            $env:HC_DB_PATH = $dbPath
            $env:SQLALCHEMY_DATABASE_URI = $dbUri
            $env:PORT = "$port"
            Start-Process -FilePath $python -ArgumentList "run.py" -WorkingDirectory $repo -WindowStyle Hidden | Out-Null
            Write-Log "started server process"
        } catch {
            Write-Log "failed to start server process"
        }
    }

    try {
        Invoke-WebRequest -Uri $healthUrl -TimeoutSec 4 | Out-Null
    } catch {
        Write-Log "health check failed"
    }

    Start-Sleep -Seconds 3
}
