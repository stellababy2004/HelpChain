param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host ""
    Write-Host "HelpChain Dev Commands"
    Write-Host "----------------------"
    Write-Host "bootstrap       Setup local DB, schema, admin and doctor checks"
    Write-Host "run             Start local server"
    Write-Host "run-debug       Start local server in debug mode (auto reload)"
    Write-Host "logs            Stream local server logs (tail)"
    Write-Host "doctor          Run environment diagnostics"
    Write-Host "smoke           Run smoke tests"
    Write-Host "smoke-verbose   Run smoke tests (verbose)"
    Write-Host "smoke-collect   List smoke tests without running"
    Write-Host "watch-tests     Run pytest automatically when files change"
    Write-Host "stop-dev        Stop integrated dev environment processes"
    Write-Host "go-no-go        Run full readiness check"
    Write-Host "scan-secrets    Scan repo for possible credentials"
    Write-Host "reset-admin     Reset local admin (requires ADMIN_PASSWORD env var)"
    Write-Host "help            Show this help"
    Write-Host ""
}

switch ($Command) {

    "help" {
        Show-Help
    }

    "bootstrap" {
        powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
    }

    "run" {
        powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
    }

    "run-debug" {
        Write-Host "Starting HelpChain in DEBUG mode..."
        $env:FLASK_ENV = "development"
        $env:FLASK_DEBUG = "1"
        powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
    }

    "logs" {
        $logPath = Join-Path (Get-Location) "logs\helpchain-dev.log"
        if (-not (Test-Path $logPath)) {
            Write-Host ""
            Write-Host "No log file found at: $logPath"
            Write-Host "Start server first with: powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 run-debug"
            Write-Host ""
            exit 1
        }

        Write-Host "Starting HelpChain log stream..."
        Get-Content -Path $logPath -Wait -Tail 50
    }

    "doctor" {
        powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1
    }

    "doctor-deep" {
        .\.venv\Scripts\python.exe .\scripts\helpchain_doctor.py
    }

    "smoke" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1
    }

    "smoke-verbose" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1 -Verbose
    }

    "smoke-collect" {
        powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1 -CollectOnly
    }

    "watch-tests" {
        $pythonExe = ".\.venv\Scripts\python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "ERROR: Python executable not found at $pythonExe"
            exit 1
        }

        $projectRoot = (Get-Location).Path
        $watchDirs = @(
            (Join-Path $projectRoot "backend"),
            (Join-Path $projectRoot "tests")
        ) | Where-Object { Test-Path $_ }

        if ($watchDirs.Count -eq 0) {
            Write-Host "ERROR: No watch directories found (backend/, tests/)."
            exit 1
        }

        $global:HCWatchPending = $false
        $global:HCWatchLastChange = [DateTime]::MinValue
        $global:HCWatchLastPath = ""
        $debounceMs = 1500
        $watchers = @()
        $eventNames = @()

        foreach ($dir in $watchDirs) {
            $fsw = New-Object System.IO.FileSystemWatcher
            $fsw.Path = $dir
            $fsw.Filter = "*.*"
            $fsw.IncludeSubdirectories = $true
            $fsw.NotifyFilter = [System.IO.NotifyFilters]'FileName, LastWrite, DirectoryName'
            $fsw.EnableRaisingEvents = $true
            $watchers += $fsw

            $changedAction = {
                $name = $Event.SourceEventArgs.Name
                if ($name -match '\.(py|html|jinja|jinja2|css|js|json|yml|yaml|toml|ini)$') {
                    $global:HCWatchPending = $true
                    $global:HCWatchLastChange = Get-Date
                    $global:HCWatchLastPath = $Event.SourceEventArgs.FullPath
                }
            }

            $ev1 = "HCWatchChanged_" + [guid]::NewGuid().ToString("N")
            $ev2 = "HCWatchCreated_" + [guid]::NewGuid().ToString("N")
            $ev3 = "HCWatchDeleted_" + [guid]::NewGuid().ToString("N")
            $ev4 = "HCWatchRenamed_" + [guid]::NewGuid().ToString("N")

            Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier $ev1 -Action $changedAction | Out-Null
            Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier $ev2 -Action $changedAction | Out-Null
            Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier $ev3 -Action $changedAction | Out-Null
            Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier $ev4 -Action $changedAction | Out-Null
            $eventNames += @($ev1, $ev2, $ev3, $ev4)
        }

        Write-Host "Watching HelpChain source files for changes..."
        Write-Host "Press Ctrl+C to stop."

        try {
            while ($true) {
                Start-Sleep -Milliseconds 250
                if (-not $global:HCWatchPending) {
                    continue
                }

                $elapsed = (Get-Date) - $global:HCWatchLastChange
                if ($elapsed.TotalMilliseconds -lt $debounceMs) {
                    continue
                }

                $global:HCWatchPending = $false

                Write-Host ""
                Write-Host ("File changed: {0}" -f $global:HCWatchLastPath)
                Write-Host "Running tests..."
                & $pythonExe -m pytest -q
                Write-Host ""
            }
        }
        finally {
            foreach ($name in $eventNames) {
                Unregister-Event -SourceIdentifier $name -ErrorAction SilentlyContinue
            }
            foreach ($fsw in $watchers) {
                try { $fsw.EnableRaisingEvents = $false } catch {}
                try { $fsw.Dispose() } catch {}
            }
        }
    }

    "stop-dev" {
        Write-Host "Stopping HelpChain dev environment..."

        $projectRoot = (Get-Location).Path
        $scriptRoot = Join-Path $projectRoot "scripts"

        $candidates = Get-CimInstance Win32_Process | Where-Object {
            ($_.ProcessId -ne $PID) -and
            $_.CommandLine -and
            (
                (
                    $_.Name -match "powershell|pwsh" -and
                    $_.CommandLine -like "*$scriptRoot*"
                ) -or
                (
                    $_.Name -match "python" -and
                    $_.CommandLine -like "*run_local.ps1*"
                )
            ) -and
            (
                $_.CommandLine -match "run_local\.ps1" -or
                $_.CommandLine -match "dev\.ps1.*run-debug" -or
                $_.CommandLine -match "dev\.ps1.*logs" -or
                $_.CommandLine -match "dev\.ps1.*watch-tests"
            )
        }

        if (-not $candidates) {
            Write-Host "No running HelpChain dev processes found."
            exit 0
        }

        foreach ($proc in $candidates) {
            $label = "HelpChain dev process"
            if ($proc.CommandLine -match "dev\.ps1.*run-debug") { $label = "run-debug" }
            elseif ($proc.CommandLine -match "dev\.ps1.*watch-tests") { $label = "watch-tests" }
            elseif ($proc.CommandLine -match "dev\.ps1.*logs") { $label = "logs" }
            elseif ($proc.CommandLine -match "run_local\.ps1") { $label = "run_local" }

            Write-Host ("Stopping process: {0} (PID {1})" -f $label, $proc.ProcessId)
            try {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            } catch {
                Write-Host ("Warning: failed to stop PID {0}: {1}" -f $proc.ProcessId, $_.Exception.Message)
            }
        }

        Write-Host "HelpChain dev environment stopped."
    }

    "go-no-go" {
        powershell -ExecutionPolicy Bypass -File .\scripts\go_no_go.ps1
    }

    "scan-secrets" {
        powershell -ExecutionPolicy Bypass -File .\scripts\scan_secrets.ps1
    }

    "reset-admin" {

        if (-not $env:ADMIN_PASSWORD) {
            Write-Host ""
            Write-Host "ERROR: ADMIN_PASSWORD env variable not set."
            Write-Host "Example:"
            Write-Host '$env:ADMIN_PASSWORD="NewStrongPassword!"'
            Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 reset-admin"
            Write-Host ""
            exit 1
        }

        .\.venv\Scripts\python.exe .\scripts\reset_admin_local.py --confirm-canonical-db
    }

    default {
        Write-Host ""
        Write-Host "Unknown command: $Command"
        Show-Help
        exit 1
    }
}
