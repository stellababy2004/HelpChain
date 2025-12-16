param(
  [Parameter(Mandatory=$true)]
  [string]$Url
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
    $resp = Invoke-WebRequest -UseBasicParsing ($base.TrimEnd('/') + $Path) -MaximumRedirection 5 -ErrorAction Stop
    $code = $resp.StatusCode
    Write-Host "$Path -> $code"
  } catch {
    $msg = $_.Exception.Message
    $status = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $status = [int]$_.Exception.Response.StatusCode
    }
    if ($status) {
      Write-Host "$Path -> ERROR ($status): $msg"
    } else {
      Write-Host "$Path -> ERROR: $msg"
    }
  }
}

"Running smoke checks for $Url"
Test-EndPoint '/'
Test-EndPoint '/health'
Test-EndPoint '/admin/login'
Test-EndPoint '/api/analytics'