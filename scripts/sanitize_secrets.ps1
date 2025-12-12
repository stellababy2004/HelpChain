#!/usr/bin/env pwsh
# Creates a backup and sanitizes common secret patterns in-place.
param(
    [string[]]$PathsToSanitize = @('.env.local','backend/error.log','logs','backend','artifacts','artifacts/vercel-output'),
    [switch]$DryRun
)
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path -Path "backups" -ChildPath "sanitized_$ts"
Write-Host "Creating backup dir: $backupDir"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# Patterns to redact
$patterns = @{
    'JWT' = 'eyJ[A-Za-z0-9_\-]{10,}'
    'OPENAI_SK' = 'sk-[A-Za-z0-9_\-]{20,100}'
    'GITHUB_PAT' = 'gh[pous]_[A-Za-z0-9_]{20,100}'
    'API_KEY_GENERIC' = '(?:AIza[0-9A-Za-z_\-]{35,}|AKIA[0-9A-Z]{16})'
}

function Sanitize-File($filePath){
    try{
        $rel = (Resolve-Path -Path $filePath).Path
    } catch { return }
    $destBackup = Join-Path $backupDir ([IO.Path]::GetFileName($filePath))
    Copy-Item -Path $filePath -Destination $destBackup -Force -ErrorAction SilentlyContinue
    $content = Get-Content -Raw -ErrorAction SilentlyContinue -LiteralPath $filePath
    if(-not $content){ return }
    foreach($k in $patterns.Keys){
        $p = $patterns[$k]
        $content = [regex]::Replace($content,$p,"REDACTED_$k")
    }
    if(-not $DryRun){ Set-Content -LiteralPath $filePath -Value $content -Force }
    Write-Host "Sanitized: $filePath"
}

# Walk targets
foreach($path in $PathsToSanitize){
    if(Test-Path $path){
        $item = Get-Item $path -Force
        if($item.PSIsContainer){
            Get-ChildItem -Path $item.FullName -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object { Sanitize-File $_.FullName }
        } else {
            Sanitize-File $item.FullName
        }
    }
}

Write-Host "Sanitization complete. Backups stored in: $backupDir"
