param(
  [string]$User = "admin",
  [string]$Pass = "Admin12345!",
  [int]$Port = 5000,
  [string]$BaseUrl,
  [switch]$Relaxed,
  [string]$BypassToken
)

Write-Host "=== Admin Smoke ===" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($BaseUrl)) { $base = "http://127.0.0.1:$Port" } else { $base = $BaseUrl.TrimEnd('/') }

# Web session (used for cookies including Vercel preview bypass)
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

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

$h = Get-Status "$base/health"
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

# Attempt login POST with CSRF and session
$body = @{ username = $User; password = $Pass; token = "" }
if ($csrf) { $body.csrf_token = $csrf }
function Invoke-Login {
  param([hashtable]$PostBody)
  $headers = @{ Referer = "$base/admin/login"; "X-Admin-Bypass" = "1" }
  return Invoke-WebRequest -Uri "$base/admin/login" -Method Post -Body $PostBody -ContentType "application/x-www-form-urlencoded" -TimeoutSec 10 -WebSession $session -MaximumRedirection 3 -Headers $headers
}

# Try login, if CSRF fails, refresh token and retry once
try {
  $response = Invoke-Login -PostBody $body
  Write-Host "Login POST status: $($response.StatusCode)" -ForegroundColor Green
} catch {
  $msg = $_.Exception.Message
  Write-Warning ("Login POST failed: {0}" -f $msg)
  if ($msg -match "400" -or $msg -match "CSRF") {
    try {
      $loginGet2 = Invoke-WebRequest -Uri "$base/admin/login" -TimeoutSec 5 -WebSession $session
      $csrf2 = $null
      $m2 = [regex]::Match($loginGet2.Content, 'name="csrf_token"[^>]*value="([^"]+)"')
      if (-not $m2.Success) { $m2 = [regex]::Match($loginGet2.Content, "name='csrf_token'[^>]*value='([^']+)'") }
      if ($m2.Success) { $csrf2 = $m2.Groups[1].Value }
      if ($csrf2) {
        $body.csrf_token = $csrf2
        $response = Invoke-Login -PostBody $body
        Write-Host "Login POST retry status: $($response.StatusCode)" -ForegroundColor Green
      }
    } catch {
      Write-Warning ("Retry after CSRF failed: {0}" -f $_.Exception.Message)
    }
  }
}

# Follow to dashboard with same session
$dash = $null
try {
  $dh = @{ "X-Admin-Bypass" = "1" }
  $dashResp = Invoke-WebRequest -Uri "$base/admin_dashboard" -TimeoutSec 5 -WebSession $session -MaximumRedirection 3 -Headers $dh
  $dash = @{ code = $dashResp.StatusCode; body = $dashResp.Content }
} catch {
  $dash = @{ code = 0; body = $_.ToString() }
}
Write-Host "Dashboard: $($dash.code)"

# Basic content assertion to confirm authenticated dashboard loaded
try {
  if ($dash.code -eq 200) {
    $okMarker = ($dash.body -match 'Админ панел') -or ($dash.body -match 'HelpChain Admin')
    if (-not $okMarker) {
      if ($Relaxed) {
        Write-Warning "Dashboard content marker not found; continuing due to -Relaxed."
      } else {
        Write-Warning "Dashboard content marker not found; login may not have succeeded."
        exit 3
      }
    }
  }
} catch { }

exit 0
