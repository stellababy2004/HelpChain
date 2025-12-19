param(
  [int]$Port = 5000,
  [string]$BaseUrl,
  [string]$Name = "Test User",
  [string]$Email = "test.user+smoke@helpchain.live",
  [string]$Category = "technical",
  [string]$Location = "Sofia",
  [string]$Problem = "Automated smoke test submission",
  [string]$BypassToken,
  [switch]$Relaxed
)

Write-Host "=== E2E Submit Request Smoke ===" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($BaseUrl)) { $base = "http://127.0.0.1:$Port" } else { $base = $BaseUrl.TrimEnd('/') }

# Use a single session to keep cookies/CSRF aligned
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

# 1) Health check (prefer Node health on Vercel)
$h = Get-Status "$base/api/_health"
if ($h.code -ne 200) { $h = Get-Status "$base/health" }
Write-Host "Health: $($h.code)"
if ($h.code -ne 200) { Write-Warning "Health not OK, aborting."; exit 1 }

# 2) Load form and extract CSRF
try {
  $formGet = Invoke-WebRequest -Uri "$base/submit_request" -TimeoutSec 8 -WebSession $session
} catch {
  Write-Host "GET /submit_request failed: $($_.Exception.Message)" -ForegroundColor Red
  if ($Relaxed) { Write-Warning "Relaxed: continuing despite form GET failure." } else { exit 1 }
}
$csrf = $null
try {
  $m = [regex]::Match($formGet.Content, 'name="csrf_token"[^>]*value="([^"]+)"')
  if (-not $m.Success) { $m = [regex]::Match($formGet.Content, "name='csrf_token'[^>]*value='([^']+)'") }
  if ($m.Success) { $csrf = $m.Groups[1].Value }
} catch {}
if (-not $csrf) { Write-Warning "CSRF token not found; POST may fail." }

# 3) POST submit_request (respect simple captcha: 7G5K)
$body = @{
  name = $Name
  email = $Email
  category = $Category
  location = $Location
  problem = $Problem
  terms = "on"
  captcha = "7G5K"
}
if ($csrf) { $body.csrf_token = $csrf }

$headers = @{ Referer = "$base/submit_request" }

try {
  $postResp = Invoke-WebRequest -Uri "$base/submit_request" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded" -TimeoutSec 10 -WebSession $session -MaximumRedirection 3 -Headers $headers
  Write-Host "Submit POST status: $([int]$postResp.StatusCode)" -ForegroundColor Green
} catch {
  $msg = $_.Exception.Message
  Write-Warning ("Submit POST failed: {0}" -f $msg)
  if ($msg -match "400" -or $msg -match "CSRF") {
    # Retry once with fresh CSRF
    try {
      $formGet2 = Invoke-WebRequest -Uri "$base/submit_request" -TimeoutSec 8 -WebSession $session
      $m2 = [regex]::Match($formGet2.Content, 'name="csrf_token"[^>]*value="([^"]+)"')
      if (-not $m2.Success) { $m2 = [regex]::Match($formGet2.Content, "name='csrf_token'[^>]*value='([^']+)'") }
      if ($m2.Success) { $body.csrf_token = $m2.Groups[1].Value }
      $postResp = Invoke-WebRequest -Uri "$base/submit_request" -Method Post -Body $body -ContentType "application/x-www-form-urlencoded" -TimeoutSec 10 -WebSession $session -MaximumRedirection 3 -Headers $headers
      Write-Host "Submit POST retry status: $([int]$postResp.StatusCode)" -ForegroundColor Green
    } catch {
      Write-Error ("Retry failed: {0}" -f $_.Exception.Message)
      exit 2
    }
  } else {
    if ($Relaxed) { Write-Warning "Relaxed: continuing despite submit POST failure." } else { exit 2 }
  }
}

# 4) Basic success heuristic: redirect or index content
try {
  $index = Invoke-WebRequest -Uri "$base/" -TimeoutSec 8 -WebSession $session
  Write-Host "Index after submit: $([int]$index.StatusCode)"
} catch {}

Write-Host "E2E submit smoke completed." -ForegroundColor Cyan
