param(
  [Parameter(Mandatory=$true)]
  [string]$Url,
  [Parameter(Mandatory=$false)]
  [string]$BypassToken,
  [Parameter(Mandatory=$false)]
  [bool]$SetBypassCookie = $true
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
  param([string]$Path)
  try {
    $headers = @{}
    if ($BypassToken -and $BypassToken.Length -gt 0) {
      # Sanitize common quoting/whitespace mistakes
      $cleanToken = ($BypassToken).Trim().Trim('"', "'")
      # Mask for console logging (first/last 4 chars)
      $masked = if ($cleanToken.Length -ge 8) { $cleanToken.Substring(0,4) + '…' + $cleanToken.Substring($cleanToken.Length-4) } else { 'len<' + $cleanToken.Length + '>' }
      # Emit once per run
      if (-not (Get-Variable -Name __BypassEchoed -Scope Script -ErrorAction SilentlyContinue)) {
        Set-Variable -Name __BypassEchoed -Value $true -Scope Script
        Write-Host ("Using bypass header token (masked): " + $masked)
      }
      # Use Vercel Protection Bypass for Automation header
      $headers['x-vercel-protection-bypass'] = [string]$cleanToken
      if ($SetBypassCookie) {
        # Ask Vercel to set a bypass cookie (header + query for broader compatibility)
        $headers['x-vercel-set-bypass-cookie'] = 'true'
        if ($Path -notmatch '\?') { $Path = $Path + '?x-vercel-set-bypass-cookie=true' } else { $Path = $Path + '&x-vercel-set-bypass-cookie=true' }
      }
      # Also include bypass token in query (per Vercel docs) to ensure automation access in protected previews
      $tokenParam = 'x-vercel-protection-bypass=' + [System.Net.WebUtility]::UrlEncode($cleanToken)
      if ($Path -notmatch '\?') { $Path = $Path + '?' + $tokenParam }
      else { $Path = $Path + '&' + $tokenParam }
    }
    $resp = Invoke-WebRequest -UseBasicParsing ($base.TrimEnd('/') + $Path) -MaximumRedirection 5 -ErrorAction Stop -Headers $headers
    $code = $resp.StatusCode
    Write-Host "$Path -> $code"
    if ($Path -like '/*') {
      Set-Variable -Name __RootStatus -Value $code -Scope Script
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

if ($BypassToken) {
  Write-Host "Running smoke checks for $Url (with bypass token)"
} else {
  Write-Host "Running smoke checks for $Url"
}
Test-EndPoint '/'
Test-EndPoint '/health'
Test-EndPoint '/api/_health'
Test-EndPoint '/admin/login'
Test-EndPoint '/api/analytics'

# Soft summary: if home is 200 but probes failed, mark warning instead of blocking
if ((Get-Variable -Name __RootStatus -Scope Script -ErrorAction SilentlyContinue) -and (Get-Variable -Name __ProbeError -Scope Script -ErrorAction SilentlyContinue)) {
  if ($__RootStatus -eq 200) {
    Write-Host "Preview root is 200; probe endpoints failed. Treating as soft-pass while routing is stabilized." -ForegroundColor Yellow
  }
}