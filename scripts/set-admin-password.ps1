param(
    [string]$Username = "admin",
    [string]$Email = "admin@helpchain.live",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

$Root = "c:\dev\HelpChain.bg"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$InitAdmin = Join-Path $Root "init_admin.py"

if (!(Test-Path $Python)) {
    throw "Python not found: $Python"
}
if (!(Test-Path $InitAdmin)) {
    throw "init_admin.py not found: $InitAdmin"
}

$env:PYTHONIOENCODING = "utf-8"

Set-Location $Root
& $Python $InitAdmin --username $Username --email $Email --password $Password
if ($LASTEXITCODE -ne 0) {
    throw "Failed to set admin password (exit=$LASTEXITCODE)"
}

Write-Output "Admin credentials updated for username '$Username'."

