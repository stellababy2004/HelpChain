param(
  [string]$User = "admin",
  [string]$Pass,
  [int]$Port = 5000,
  [string]$BaseUrl,
  [switch]$Relaxed,
  [string]$BypassToken
)

Write-Host "=== Admin Smoke ===" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($BaseUrl)) { $base = "http://127.0.0.1:$Port" } else { $base = $BaseUrl.TrimEnd('/') }

# Web session (used for cookies including Vercel preview bypass)
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# If no explicit token, read from env
if (-not $BypassToken -and $env:VERCEL_PROTECTION_BYPASS) { $BypassToken = $env:VERCEL_PROTECTION_BYPASS }

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
try {
  $loginGet = Invoke-WebRequest -Uri "$base/admin/login" -TimeoutSec 5 -WebSession $session
} catch {
  Write-Host "Login GET failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

# Extract CSRF token from hidden input (tolerate different quote/spacing)
$csrf = $null
try {
  $m = [regex]::Match($loginGet.Content, 'name="csrf_token"[^>]*value="([^"]+)"')
  if (-not $m.Success) {
    $m = [regex]::Match($loginGet.Content, "name='csrf_token'[^>]*value='([^']+)'")
  }
  if ($m.Success) { $csrf = $m.Groups[1].Value }
} catch { }
if (-not $csrf) {
  Write-Warning "CSRF token not found in login form; POST may fail."
  try { Write-Host ($loginGet.Content.Substring(0, [Math]::Min(400, $loginGet.Content.Length))) } catch { }
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
    Write-Host "Login POST status (pw attempt): $($resp.StatusCode)" -ForegroundColor Green
  } catch {
    $msg = $_.Exception.Message
    Write-Warning ("Login POST failed (pw attempt): {0}" -f $msg)
    if ($msg -match "400" -or $msg -match "CSRF") {
      try {
        $loginGet2 = Invoke-WebRequest -Uri "$base/admin/login" -TimeoutSec 5 -WebSession $session
        $csrf2 = $null
        $m2 = [regex]::Match($loginGet2.Content, 'name="csrf_token"[^>]*value="([^"]+)"')
        if (-not $m2.Success) { $m2 = [regex]::Match($loginGet2.Content, "name='csrf_token'[^>]*value='([^']+)'") }
        if ($m2.Success) { $csrf2 = $m2.Groups[1].Value }
        if ($csrf2) {
          $post.csrf_token = $csrf2
          $resp = Invoke-Login -PostBody $post
          Write-Host "Login POST retry status: $($resp.StatusCode)" -ForegroundColor Green
        }
      } catch {
        Write-Warning ("Retry after CSRF failed: {0}" -f $_.Exception.Message)
      }
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
  if ($Relaxed) {
    Write-Warning "Dashboard content marker not found after trying fallback passwords; continuing due to -Relaxed."
  } else {
    Write-Warning "Dashboard content marker not found; login may not have succeeded."
    exit 3
  }
}

exit 0
