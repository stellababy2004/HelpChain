$backup = Join-Path $env:TEMP ('helpchain_testdb_backup_' + (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -Path $backup -ItemType Directory -Force | Out-Null
$files = Get-ChildItem -Path $env:TEMP -Filter '*_test.db' -Recurse -ErrorAction SilentlyContinue
if (-not $files) {
    Write-Output 'No files to move'
    exit 0
}
$cnt = $files.Count
$files | Move-Item -Destination $backup -Force -ErrorAction SilentlyContinue
$moved = Get-ChildItem -Path $backup -Filter '*_test.db' -Recurse -ErrorAction SilentlyContinue
$movedCount = if ($moved) { $moved.Count } else { 0 }
Write-Output "Moved:$movedCount"
Write-Output "Backup:$backup"
