$source = "C:\dev\HelpChain.bg\instance\hc_local_dev.db"
$target = "C:\dev\HelpChain.bg\instance\hc_local_dev.backup.db"

if (!(Test-Path $source)) {
    Write-Host "Source DB not found: $source"
    exit 1
}

Copy-Item $source $target -Force
Write-Host "Backup done: $target"