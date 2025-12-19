param(
  [string]$Branch,
  [int]$Limit = 400,
  [string]$OrgId,
  [string]$ProjectId,
  [string]$Token,
  [switch]$ForceV6,
  [switch]$VerboseErrors,
  [int]$WaitReadySeconds = 0,
  [int]$PollIntervalSeconds = 10
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
  # Sanitize token to avoid non-ASCII/header errors caused by copy-paste
  try {
    $Token = [string]$Token
    $Token = $Token.Trim()
    if ($Token.StartsWith('"') -and $Token.EndsWith('"')) { $Token = $Token.Substring(1, $Token.Length - 2) }
    if ($Token.StartsWith("'") -and $Token.EndsWith("'")) { $Token = $Token.Substring(1, $Token.Length - 2) }
    # Remove CR/LF and tabs
    $Token = $Token -replace "\r|\n|\t", ''
    # Validate ASCII
    if ([System.Text.Encoding]::UTF8.GetByteCount($Token) -ne $Token.Length) {
      Write-Err 'Vercel API token contains non-ASCII characters. Re-copy as plain text (no quotes).'
      exit 2
    }
  } catch {
    Write-Err ("Failed to sanitize token: {0}" -f $_.Exception.Message)
    exit 2
  }

  $headers = @{ Authorization = "Bearer $Token" }
  $api = 'https://api.vercel.com'

  Write-Info "Fetching latest preview deployment for branch '$Branch'..."
  $deploy = $null
  function Invoke-Api {
    param([string]$Uri)
    try {
      return Invoke-RestMethod -Uri $Uri -Headers $headers -Method Get -ErrorAction Stop
    } catch {
      if ($VerboseErrors -and $_.ErrorDetails -and $_.ErrorDetails.Message) {
        Write-Warn ("API error body: {0}" -f $_.ErrorDetails.Message)
      }
      throw
    }
  }

  $q = @{
    projectId = $ProjectId
    limit     = 1
    target    = 'preview'
    'meta-git-branch' = $Branch
  }
  $parts = $q.GetEnumerator() |
    ForEach-Object { '{0}={1}' -f $_.Key, [System.Uri]::EscapeDataString([string]$_.Value) } |
    Sort-Object

  if ($ForceV6) {
    try {
      $uri = "$api/v6/deployments?" + ($parts -join '&')
      $resp = Invoke-Api -Uri $uri
      if ($resp.deployments -and $resp.deployments.Count -gt 0) { $deploy = $resp.deployments[0] }
    } catch {
      Write-Err ("v6 deployments query failed: {0}" -f $_.Exception.Message)
      exit 4
    }
  } else {
    try {
      $uri13 = "$api/v13/deployments?" + ($parts -join '&')
      $resp13 = Invoke-Api -Uri $uri13
      if ($resp13.deployments -and $resp13.deployments.Count -gt 0) { $deploy = $resp13.deployments[0] }
    } catch {
      Write-Warn ("v13 deployments query failed: {0}" -f $_.Exception.Message)
    }
    if (-not $deploy) {
      try {
        $uri6 = "$api/v6/deployments?" + ($parts -join '&')
        $resp6 = Invoke-Api -Uri $uri6
        if ($resp6.deployments -and $resp6.deployments.Count -gt 0) { $deploy = $resp6.deployments[0] }
      } catch {
        Write-Err ("v6 deployments query failed: {0}" -f $_.Exception.Message)
        exit 4
      }
    }
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

  # Optional wait until deployment leaves BUILDING/QUEUED and becomes READY/ERROR
  if ($WaitReadySeconds -gt 0) {
    $deadline = (Get-Date).AddSeconds($WaitReadySeconds)
    while ((Get-Date) -lt $deadline) {
      try {
        $uriState = "$api/v13/deployments/$id"
        $d = Invoke-Api -Uri $uriState
        $state = $d.readyState
        if (-not $state) { $state = $d.state }
        Write-Info ("State: {0}" -f $state)
        if ($state -in @('READY','ERROR','CANCELED','FAILED')) { break }
      } catch {
        Write-Warn ("state poll failed: {0}" -f $_.Exception.Message)
      }
      Start-Sleep -Seconds ([Math]::Max(2, $PollIntervalSeconds))
    }
  }

  # Try v13 events first, then v6 (or force v6)
  $events = $null
  if ($ForceV6) {
    try {
      $uri = "$api/v6/deployments/$id/events?limit=$Limit"
      $events = Invoke-Api -Uri $uri
    } catch { Write-Err ("v6 events fetch failed: {0}" -f $_.Exception.Message); exit 4 }
  } else {
    try {
      $uri = "$api/v13/deployments/$id/events?limit=$Limit"
      $events = Invoke-Api -Uri $uri
    } catch { Write-Warn ("v13 events fetch failed: {0}" -f $_.Exception.Message) }
    if (-not $events) {
      try {
        $uri = "$api/v6/deployments/$id/events?limit=$Limit"
        $events = Invoke-Api -Uri $uri
      } catch { Write-Err ("v6 events fetch failed: {0}" -f $_.Exception.Message); exit 4 }
    }
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
