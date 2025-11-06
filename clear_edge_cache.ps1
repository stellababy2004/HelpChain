# Clear Microsoft Edge Cache Script
# This script clears the cache, cookies, and browsing data for Microsoft Edge

Write-Host "Clearing Microsoft Edge cache and browsing data..." -ForegroundColor Yellow

# Stop Edge processes
Write-Host "Stopping Edge processes..." -ForegroundColor Cyan
Get-Process -Name "msedge" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "MicrosoftEdge" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "MicrosoftEdgeCP" -ErrorAction SilentlyContinue | Stop-Process -Force

# Wait a moment
Start-Sleep -Seconds 2

# Define Edge user data paths
$edgePaths = @(
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Code Cache",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\GPUCache",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Storage\ext",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Session Storage",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Local Storage",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\IndexedDB",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Service Worker"
)

# Clear cache directories
foreach ($path in $edgePaths) {
    if (Test-Path $path) {
        Write-Host "Clearing: $path" -ForegroundColor Green
        try {
            Remove-Item -Path $path -Recurse -Force -ErrorAction Stop
            Write-Host "✓ Cleared successfully" -ForegroundColor Green
        }
        catch {
            Write-Host "✗ Failed to clear: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    else {
        Write-Host "Path not found: $path" -ForegroundColor Gray
    }
}

# Alternative method using Edge's built-in clear command (if available)
Write-Host "`nTrying Edge's built-in cache clear..." -ForegroundColor Cyan
try {
    # Launch Edge with cache clear flags (this might not work in all versions)
    Start-Process "msedge.exe" -ArgumentList "--clear-cache", "--disable-features=VizDisplayCompositor" -Wait -NoNewWindow
    Write-Host "✓ Edge cache clear command executed" -ForegroundColor Green
}
catch {
    Write-Host "✗ Edge built-in clear failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Clear additional cache locations
$additionalPaths = @(
    "$env:TEMP\MicrosoftEdge",
    "$env:TEMP\Edge",
    "$env:APPDATA\Microsoft\Windows\INetCache\IE"  # Sometimes shared with IE
)

foreach ($path in $additionalPaths) {
    if (Test-Path $path) {
        Write-Host "Clearing additional cache: $path" -ForegroundColor Green
        try {
            Remove-Item -Path $path -Recurse -Force -ErrorAction Stop
            Write-Host "✓ Additional cache cleared" -ForegroundColor Green
        }
        catch {
            Write-Host "✗ Failed to clear additional cache: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

Write-Host "`nCache clearing completed!" -ForegroundColor Yellow
Write-Host "You can now restart Microsoft Edge." -ForegroundColor Cyan

# Optional: Ask to restart Edge
$restart = Read-Host "Would you like to restart Microsoft Edge now? (y/n)"
if ($restart -eq 'y' -or $restart -eq 'Y') {
    Write-Host "Starting Microsoft Edge..." -ForegroundColor Cyan
    Start-Process "msedge.exe"
}
else {
    Write-Host "Please restart Microsoft Edge manually." -ForegroundColor Cyan
}
