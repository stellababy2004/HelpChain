param(
  [string]$User = "admin",
  [string]$Pass,
  [int]$Port = 5000,
  [string]$BaseUrl,
  [switch]$Relaxed,
  [switch]$Strict = $true,
  [string]$BypassToken
)

Write-Host "=== Admin Smoke ===" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  $base = "http://127.0.0.1:$Port"
} else {
  $base = $BaseUrl.TrimEnd('/')
  # Basic validation to avoid malformed inputs like "https:80"
  if ($base -notmatch '^(https?://)') {
    Write-Error "BaseUrl must include scheme, e.g., https://your-preview.vercel.app"
    exit 1
  }
}

# Web session (used for cookies including Vercel preview bypass)
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# If no explicit token, read from env (support both common env names)
if (-not $BypassToken) {
  if ($env:BYPASS_TOKEN) { $BypassToken = $env:BYPASS_TOKEN }
  elseif ($env:VERCEL_PROTECTION_BYPASS) { $BypassToken = $env:VERCEL_PROTECTION_BYPASS }
}

# If preview protection token provided, set signed cookie via official flow
if ($BypassToken) {
  try {
    $bypassUrl = "$base/?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=$BypassToken"
    Invoke-WebRequest -Uri $bypassUrl -UseBasicParsing -TimeoutSec 10 -WebSession $session -MaximumRedirection 3 | Out-Null
  } catch {
    Write-Warning ("Bypass cookie setup failed (continuing): {0}" -f $_.Exception.Message)
  }
}

function Get-Status($url) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop -WebSession $session
    return @{ code = $r.StatusCode; body = $r.Content }
  } catch {
    return @{ code = 0; body = $_.ToString() }
  }
}

# Prefer Node health endpoint on Vercel, fallback to /health
$h = Get-Status "$base/api/_health"
if ($h.code -ne 200) {
  $h = Get-Status "$base/health"
}
Write-Host "Health: $($h.code) $($h.body)"

# Reset admin password and disable 2FA (dev-only routes)
# Use the existing session so bypass cookies persist
try {
  $resetResp = Invoke-WebRequest -Uri "$base/admin/dev_reset" -TimeoutSec 5 -WebSession $session -MaximumRedirection 3
} catch { $resetResp = $null }
Write-Host "Reset: $([int]($resetResp.StatusCode))"
try {
  $disableResp = Invoke-WebRequest -Uri "$base/admin/dev_disable_2fa" -TimeoutSec 5 -WebSession $session -MaximumRedirection 3
} catch { $disableResp = $null }
Write-Host "Disable 2FA: $([int]($disableResp.StatusCode))"

# Keep using the same session for login

# Fetch login page to get cookies and CSRF token
$loginUrl = "$base/admin/login"
Write-Host "LOGIN_URL=$loginUrl"
try {
  $loginGet = Invoke-WebRequest -Uri $loginUrl -TimeoutSec 5 -WebSession $session
} catch {
  Write-Host "Login GET failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

# Extract CSRF token (robust):
# - input name/value in any order
# - double or single quotes
# - optional meta tag fallback
# - final fallback: CSRF-like cookie names
$csrf = $null
try {
  $patterns = @(
    'name=["'']csrf_token["''][^>]*value=["'']([^"'']+)["'']',
    'value=["'']([^"'']+)["''][^>]*name=["'']csrf_token["'']',
    '<meta[^>]*name=["'']csrf[-_]?token["''][^>]*content=["'']([^"'']+)["'']'
  )
  foreach ($pat in $patterns) {
    $m = [regex]::Match($loginGet.Content, $pat, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) { $csrf = $m.Groups[1].Value; break }
  }
  if (-not $csrf) {
    $cookieNames = @('csrf_token','XSRF-TOKEN','CSRF-TOKEN','_csrf')
    foreach ($c in $session.Cookies) {
      if ($cookieNames -contains $c.Name) { $csrf = $c.Value; break }
    }
  }
} catch { }
if (-not $csrf) {
  if ($Strict -and -not $Relaxed) {
    Write-Error "Strict mode: CSRF token not found in login form (fallback form likely missing hidden csrf input)."
    try { Write-Host ($loginGet.Content.Substring(0, [Math]::Min(600, $loginGet.Content.Length))) } catch { }
    exit 2
  } else {
    Write-Warning "CSRF token not found in login form; continuing (Relaxed)."
    try { Write-Host ($loginGet.Content.Substring(0, [Math]::Min(400, $loginGet.Content.Length))) } catch { }
  }
}

# Determine passwords to try (param > env > common defaults)
$passwordsToTry = @()
if ($Pass) { $passwordsToTry += $Pass }
elseif ($env:ADMIN_USER_PASSWORD) { $passwordsToTry += $env:ADMIN_USER_PASSWORD }
else { $passwordsToTry += @("Admin12345!", "Admin123") }

function Invoke-Login {
  param([hashtable]$PostBody)
  $headers = @{ Referer = "$base/admin/login"; "X-Admin-Bypass" = "1" }
  return Invoke-WebRequest -Uri "$base/admin/login" -Method Post -Body $PostBody -ContentType "application/x-www-form-urlencoded" -TimeoutSec 15 -WebSession $session -MaximumRedirection 3 -Headers $headers
}

function Try-Login-And-CheckDashboard {
  param([string]$Password)
  # Fresh body per attempt
  $post = @{ username = $User; password = $Password; token = "" }
  if ($csrf) { $post.csrf_token = $csrf }
  try {
    $resp = Invoke-Login -PostBody $post
    $code = [int]$resp.StatusCode
    Write-Host "Login POST status: $code" -ForegroundColor Green
    if ($Strict -and -not $Relaxed) {
      if ($code -eq 400) { Write-Error "Strict mode: POST returned 400 (likely CSRF validation failure)."; return $false }
      if ($code -ne 302 -and $code -ne 303 -and $code -ne 200) {
        Write-Error ("Strict mode: Unexpected login response code: {0}" -f $code); return $false
      }
    }
  } catch {
    $msg = $_.Exception.Message
    Write-Warning ("Login POST failed: {0}" -f $msg)
    if ($Strict -and -not $Relaxed) { return $false }
    # Relaxed path: attempt one retry after refreshing CSRF
    try {
      $loginGet2 = Invoke-WebRequest -Uri "$base/admin/login" -TimeoutSec 5 -WebSession $session
      $csrf2 = $null
      $pats = @(
        'name=["'']csrf_token["''][^>]*value=["'']([^"'']+)["'']',
        'value=["'']([^"'']+)["''][^>]*name=["'']csrf_token["'']'
      )
      foreach ($pat in $pats) {
        $m2 = [regex]::Match($loginGet2.Content, $pat, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($m2.Success) { $csrf2 = $m2.Groups[1].Value; break }
      }
      if ($csrf2) {
        $post.csrf_token = $csrf2
        $resp = Invoke-Login -PostBody $post
        Write-Host "Login POST retry status: $($resp.StatusCode)" -ForegroundColor Green
      }
    } catch {
      Write-Warning ("Retry after CSRF failed: {0}" -f $_.Exception.Message)
    }
  }
  # Fetch dashboard
  try {
    $dh = @{ "X-Admin-Bypass" = "1" }
    $dashResp = Invoke-WebRequest -Uri "$base/admin_dashboard" -TimeoutSec 10 -WebSession $session -MaximumRedirection 3 -Headers $dh
    $code = [int]$dashResp.StatusCode
    $body = $dashResp.Content
    Write-Host "Dashboard: $code"
  } catch {
    $code = 0
    $body = $_.ToString()
  }
  if ($code -ne 200) { return $false }
  # Content markers (Bulgarian title, EN label, or welcome text)
  $okMarker = ($body -match 'Админ панел') -or ($body -match 'HelpChain Admin') -or ($body -match 'административния панел')
  # Detect Vercel Instant Preview fallback to aid debugging
  if (-not $okMarker -and ($body -match 'Instant Preview' -or $body -match 'Deployment has failed')) {
    Write-Warning "Preview returned Vercel Instant Preview/failure page; deployment may not be ready."
  }
  return [bool]$okMarker
}

$success = $false
foreach ($pw in $passwordsToTry) {
  Write-Host ("Trying login with password candidate: {0}" -f ($pw -replace '(?s).', '*'))
  if (Try-Login-And-CheckDashboard -Password $pw) { $success = $true; break }
}

if (-not $success) {
  if ($Strict -and -not $Relaxed) {
    Write-Error "Strict mode: Dashboard marker not found or login flow failed."
    exit 3
  } else {
    Write-Warning "Dashboard content marker not found; continuing due to Relaxed mode."
  }
}

exit 0
