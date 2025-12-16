param(
  [Parameter(Mandatory=$true)]
  [string]$Url,
  [Parameter(Mandatory=$false)]
  [string]$BypassToken
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
      # Use Vercel Protection Bypass for Automation header
      $headers['x-vercel-protection-bypass'] = $BypassToken
      # Optionally ask Vercel to set a bypass cookie for browser follow-ups
      $headers['x-vercel-set-bypass-cookie'] = 'true'
    }
    $resp = Invoke-WebRequest -UseBasicParsing ($base.TrimEnd('/') + $Path) -MaximumRedirection 5 -ErrorAction Stop -Headers $headers
    $code = $resp.StatusCode
    Write-Host "$Path -> $code"
  } catch {
    $msg = $_.Exception.Message
    $status = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $status = [int]$_.Exception.Response.StatusCode
    }
    if ($status) {
      if ($status -eq 401) {
        Write-Host "$Path -> ERROR (401): Preview Protection active. Use -BypassToken with the project 'Protection Bypass for Automation' secret, or open the Shareable Link in a browser to set the cookie." -ForegroundColor Yellow
      } else {
        Write-Host "$Path -> ERROR ($status): $msg"
      }
    } else {
      Write-Host "$Path -> ERROR: $msg"
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
Test-EndPoint '/admin/login'
Test-EndPoint '/api/analytics'