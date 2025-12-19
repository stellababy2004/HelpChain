param(
  [string]$Branch,
  [int]$Limit = 400,
  [string]$OrgId,
  [string]$ProjectId,
  [string]$Token
)

$ErrorActionPreference = 'Stop'

function Write-Info($m){ Write-Host "[vercel-log] $m" -ForegroundColor Cyan }
function Write-Warn($m){ Write-Host "[vercel-log] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[vercel-log] $m" -ForegroundColor Red }

try {
  $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

  if (-not $Branch) {
    try { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() } catch { $Branch = $null }
  }
  if (-not $Branch) {
    Write-Warn 'Branch not provided and git unavailable; defaulting to "vercel-setup-health".'
    $Branch = 'vercel-setup-health'
  }

  # Read project metadata from .vercel/project.json if present
  $projFile = Join-Path $root '.vercel/project.json'
  if (-not $ProjectId -or -not $OrgId) {
    if (Test-Path $projFile) {
      $proj = Get-Content $projFile -Raw | ConvertFrom-Json
      if (-not $ProjectId -and $proj.projectId) { $ProjectId = $proj.projectId }
      if (-not $OrgId -and $proj.orgId) { $OrgId = $proj.orgId }
    }
  }

  if (-not $ProjectId) { Write-Err 'Missing ProjectId (and .vercel/project.json not found). Provide -ProjectId.'; exit 2 }
  if (-not $OrgId) { Write-Err 'Missing OrgId (and .vercel/project.json not found). Provide -OrgId.'; exit 2 }

  if (-not $Token) { $Token = $env:VERCEL_TOKEN }
  if (-not $Token) { Write-Err 'Missing Vercel API token. Set $env:VERCEL_TOKEN or pass -Token.'; exit 2 }

  $headers = @{ Authorization = "Bearer $Token" }
  $api = 'https://api.vercel.com'

  Write-Info "Fetching latest preview deployment for branch '$Branch'..."
  # Try v13 deployments API first
  $deploy = $null
  try {
    $q = @{
      projectId = $ProjectId
      limit     = 1
      target    = 'preview'
      'meta-git-branch' = $Branch
    }
    $parts = $q.GetEnumerator() |
      ForEach-Object { '{0}={1}' -f $_.Key, [System.Uri]::EscapeDataString([string]$_.Value) } |
      Sort-Object
    $uri = "$api/v13/deployments?" + ($parts -join '&')
    $resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get -ErrorAction Stop
    if ($resp.deployments -and $resp.deployments.Count -gt 0) { $deploy = $resp.deployments[0] }
  } catch {
    Write-Warn ("v13 deployments query failed: {0}" -f $_.Exception.Message)
  }

  if (-not $deploy) {
    # Fallback to v6 API
    $q = @{
      projectId = $ProjectId
      limit     = 1
      target    = 'preview'
      'meta-git-branch' = $Branch
    }
    $parts = $q.GetEnumerator() |
      ForEach-Object { '{0}={1}' -f $_.Key, [System.Uri]::EscapeDataString([string]$_.Value) } |
      Sort-Object
    $uri = "$api/v6/deployments?" + ($parts -join '&')
    $resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get -ErrorAction Stop
    if ($resp.deployments -and $resp.deployments.Count -gt 0) { $deploy = $resp.deployments[0] }
  }

  if (-not $deploy) { Write-Err "No preview deployment found for branch '$Branch'."; exit 3 }

  $id = $deploy.uid
  if (-not $id) { $id = $deploy.id }
  if (-not $id) { Write-Err 'Unable to resolve deployment id.'; exit 3 }

  $url = if ($deploy.url) { "https://$($deploy.url)" } else { $null }
  $state = $deploy.readyState
  if (-not $state) { $state = $deploy.state }
  $urlOut = if ($url) { $url } else { '(n/a)' }
  Write-Info ("Deployment: id={0} state={1} url={2}" -f $id, $state, $urlOut)

  # Try v13 events first, then v6
  $events = $null
  try {
    $uri = "$api/v13/deployments/$id/events?limit=$Limit"
    $events = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get -ErrorAction Stop
  } catch { Write-Warn ("v13 events fetch failed: {0}" -f $_.Exception.Message) }

  if (-not $events) {
    try {
      $uri = "$api/v6/deployments/$id/events?limit=$Limit"
      $events = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get -ErrorAction Stop
    } catch { Write-Err ("v6 events fetch failed: {0}" -f $_.Exception.Message); exit 4 }
  }

  Write-Info "Last $Limit build events (most recent last):"
  $items = $events.events
  if (-not $items) { $items = $events }
  foreach ($e in $items) {
    $t = $e.type
    $ts = $e.timestamp
    $msg = $null
    if ($e.payload -and $e.payload.text) { $msg = $e.payload.text }
    elseif ($e.text) { $msg = $e.text }
    elseif ($e.message) { $msg = $e.message }
    else { $msg = ($e | ConvertTo-Json -Compress) }
    if ($msg -is [string]) { $msg = $msg.Trim() }
    Write-Host ("[{0}] {1} :: {2}" -f $ts, $t, $msg)
  }

  exit 0
}
catch {
  Write-Err $_
  exit 1
}
