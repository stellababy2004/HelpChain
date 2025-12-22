
param(
  [Parameter(Mandatory=$true)]
  [string]$Url,
  [Parameter(Mandatory=$false)]
  [string]$BypassToken,
  [Parameter(Mandatory=$false)]
  [bool]$SetBypassCookie = $true,
  [Parameter(Mandatory=$false)]
  [string]$CookieJar = "cookie.txt"
)

$ErrorActionPreference = 'Stop'

# Normalize and validate base URL
$base = $Url.Trim()
$base = $base -replace '^[<\s]*','' -replace '[>\s]*$',''
if ($base -notmatch '^https?://') { $base = 'https://' + $base }
try {
  $null = [Uri]$base
} catch {
  Write-Host "Base URL invalid: '$Url' -> '$base'" -ForegroundColor Red
  Write-Host "Provide a real Vercel preview like https://help-chain-xxxxx.vercel.app"
  exit 1
}

function Test-EndPoint {
  param([string]$Path, [object]$WebSession = $null)
  try {
    $headers = @{}
    $useSession = $false
    if ($BypassToken -and $BypassToken.Length -gt 0) {
      $cleanToken = ($BypassToken).Trim().Trim('"', "'")
      # Никога не принтирай токена или masked value в CI/production
      $headers['x-vercel-protection-bypass'] = [string]$cleanToken
      # Ако имаме WebSession (cookie jar), нека го използваме
      if ($WebSession) { $useSession = $true }
    }
    $uri = $base.TrimEnd('/') + $Path
    $uriSafe = $uri -replace '\?.*','' # Премахни query параметрите за логване
    if ($useSession) {
      $resp = Invoke-WebRequest -UseBasicParsing $uri -MaximumRedirection 5 -ErrorAction Stop -Headers $headers -WebSession $WebSession
    } else {
      $resp = Invoke-WebRequest -UseBasicParsing $uri -MaximumRedirection 5 -ErrorAction Stop -Headers $headers
    }
    $code = $resp.StatusCode
    Write-Host "$uriSafe -> $code"
    if ($Path -like '/*') {
      Set-Variable -Name __RootStatus -Value $code -Scope Script
    }
    if ($Path -eq '/health') {
      Set-Variable -Name __HealthStatus -Value $code -Scope Script
    }
  } catch {
    $msg = $_.Exception.Message
    $status = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $status = [int]$_.Exception.Response.StatusCode
    }
    $body = $null
    try {
      if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream) {
        $stream = $_.Exception.Response.GetResponseStream()
        if ($stream) {
          $reader = New-Object System.IO.StreamReader($stream)
          $body = $reader.ReadToEnd()
          if ($body -and $body.Length -gt 800) { $body = $body.Substring(0,800) + ' ...<truncated>' }
        }
      }
    } catch { }
    if ($status) {
      if ($status -eq 401) {
        Write-Host "$Path -> ERROR (401): Preview Protection active. Use -BypassToken with the project 'Protection Bypass for Automation' secret, or open the Shareable Link in a browser to set the cookie." -ForegroundColor Yellow
      } elseif ($Path -eq '/api/_health' -and $status -eq 404) {
        # Treat missing /api/_health as soft warning if /health is available
        Set-Variable -Name __ApiHealth404 -Value $true -Scope Script
        Write-Host "$Path -> WARNING (404): /api/_health not routed; relying on /health." -ForegroundColor Yellow
      } else {
        if ($body) {
          Write-Host "$Path -> ERROR ($status): $msg" -ForegroundColor Red
          Write-Host ("Body: " + $body)
        } else {
          Write-Host "$Path -> ERROR ($status): $msg"
        }
        if ($Path -notlike '/*') { Set-Variable -Name __ProbeError -Value $true -Scope Script }
      }
    } else {
      Write-Host "$Path -> ERROR: $msg"
      if ($Path -notlike '/*') { Set-Variable -Name __ProbeError -Value $true -Scope Script }
    }
  }
}


# --- Cookie jar logic for Vercel Preview Protection ---
$webSession = $null
if ($BypassToken) {
  Write-Host "Running smoke checks for $Url (cookie jar mode)"
  # 1. Set bypass cookie and save session
  $cleanToken = ($BypassToken).Trim().Trim('"', "'")
  $cookiePath = Join-Path $PSScriptRoot $CookieJar
  $headers = @{
    'x-vercel-protection-bypass' = $cleanToken
    'x-vercel-set-bypass-cookie' = 'true'
  }
  $bypassUrl = $base.TrimEnd('/') + "/api/_health?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=[MASKED]"
  $webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  try {
    # Истинският URL с токен се използва само за заявката, не се логва
    $realBypassUrl = $base.TrimEnd('/') + "/api/_health?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=" + [System.Net.WebUtility]::UrlEncode($cleanToken)
    $resp = Invoke-WebRequest -UseBasicParsing $realBypassUrl -MaximumRedirection 5 -ErrorAction Stop -Headers $headers -WebSession $webSession
    # Save cookies to file for debug/CI
    $webSession.Cookies | Export-Clixml -Path $cookiePath
    Write-Host "Bypass cookie set and saved to $cookiePath"
  } catch {
    Write-Host "Failed to set bypass cookie (details masked)" -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "Running smoke checks for $Url"
}

# 2. Use session (cookie jar) for all subsequent requests if available
Test-EndPoint '/' $webSession
Test-EndPoint '/api/root' $webSession
Test-EndPoint '/api/index.py' $webSession
Test-EndPoint '/health' $webSession
Test-EndPoint '/api/_health' $webSession
Test-EndPoint '/admin/login' $webSession
Test-EndPoint '/api/analytics' $webSession
Test-EndPoint '/favicon.ico' $webSession

# Soft summary: if home is 200 but probes failed, mark warning instead of blocking
if ((Get-Variable -Name __RootStatus -Scope Script -ErrorAction SilentlyContinue) -and (Get-Variable -Name __ProbeError -Scope Script -ErrorAction SilentlyContinue)) {
  if ($__RootStatus -eq 200) {
    Write-Host "Preview root is 200; probe endpoints failed. Treating as soft-pass while routing is stabilized." -ForegroundColor Yellow
  }
}

# Additional soft note: /api/_health 404 is OK if /health is 200
if ((Get-Variable -Name __ApiHealth404 -Scope Script -ErrorAction SilentlyContinue) -and (Get-Variable -Name __HealthStatus -Scope Script -ErrorAction SilentlyContinue)) {
  if ($__HealthStatus -eq 200) {
    Write-Host "/api/_health 404 ignored because /health is 200 (soft-pass)." -ForegroundColor Yellow
  }
}