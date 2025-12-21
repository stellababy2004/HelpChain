param(
  [string]$ProjectPrefix = 'helpchainlive',
  [string]$Branch,
  [switch]$NoCommit
)

$ErrorActionPreference = 'Stop'
Write-Host '== Trigger new Vercel preview and run smokes ==' -ForegroundColor Cyan

# Resolve branch
if (-not $Branch -or [string]::IsNullOrWhiteSpace($Branch)) {
  $Branch = (git branch --show-current).Trim()
}
Write-Host ("Branch {0}" -f $Branch)

# Optional empty commit to trigger redeploy
if (-not $NoCommit) {
  $preSha = (git rev-parse HEAD).Trim()
  git commit --allow-empty -m 'chore(preview) trigger redeploy' | Out-Null
  $sha = (git rev-parse HEAD).Trim()
  Write-Host ("Commit {0} prev {1}" -f $sha,$preSha)
  git push | Out-Null
} else {
  $sha = (git rev-parse HEAD).Trim()
  Write-Host ("Using existing commit {0}" -f $sha)
}

if (-not $env:VERCEL_TOKEN) { throw 'VERCEL_TOKEN not set' }
$headers = @{ Authorization = ('Bearer {0}' -f $env:VERCEL_TOKEN) }

# Poll for READY preview matching branch + commit
$max = 60
$i = 0
$dep = $null
Write-Host 'Polling Vercel for READY preview...' -ForegroundColor Yellow
while ($i -lt $max) {
  $i++
  try {
    $resp = Invoke-WebRequest -Uri 'https://api.vercel.com/v6/deployments?limit=50' -Headers $headers -UseBasicParsing -TimeoutSec 15
    $json = $resp.Content | ConvertFrom-Json
  } catch {
    Start-Sleep -Seconds 5
    continue
  }
  $dep = $json.deployments |
    Where-Object { $_.name -like "$ProjectPrefix-*" -and $_.state -eq 'READY' } |
    Where-Object {
      $m = $_.meta
      $mb = $null
      if ($m) { $mb = ($m.githubCommitRef,$m.gitlabCommitRef,$m.bitbucketCommitRef | Where-Object { $_ })[0] }
      if (-not $mb) { $true } else { $mb -eq $Branch }
    } |
    Where-Object {
      $m = $_.meta
      $c = $null
      if ($m) { $c = ($m.githubCommitSha,$m.commitSha,$m.gitCommitSha | Where-Object { $_ })[0] }
      if (-not $c) { $false } else { $c.StartsWith($sha.Substring(0,7)) }
    } |
    Sort-Object created -Descending |
    Select-Object -First 1
  if ($dep) { break }
  Start-Sleep -Seconds 10
}
if (-not $dep) { throw 'No READY preview found for the new commit within timeout' }

$base = "https://$($dep.url)"
Write-Host ("READY preview {0}" -f $base) -ForegroundColor Green

if (-not $env:BYPASS_TOKEN) { throw 'BYPASS_TOKEN not set (protected previews)' }
$bypass = @{ 'x-vercel-protection-bypass' = $env:BYPASS_TOKEN }

# Version and health
Write-Host 'GET /api/_version'
$ver = Invoke-WebRequest -Uri ($base + '/api/_version') -Headers $bypass -UseBasicParsing -TimeoutSec 30
Write-Host $ver.Content
Write-Host 'GET /health (headers)'
$health = Invoke-WebRequest -Uri ($base + '/health') -Headers $bypass -UseBasicParsing -TimeoutSec 30
Write-Host ('X-App-Commit {0}' -f $health.Headers['X-App-Commit'])

# Strict admin smokes
Write-Host 'Running admin strict smoke...'
pwsh -File (Join-Path $PSScriptRoot 'admin-smoke.ps1') -BaseUrl $base -Strict -BypassToken $env:BYPASS_TOKEN

Write-Host 'All smokes done.' -ForegroundColor Cyan
exit 0