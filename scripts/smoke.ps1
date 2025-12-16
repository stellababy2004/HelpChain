$ErrorActionPreference = 'Stop'

param(
  [Parameter(Mandatory=$true)]
  [string]$Url
)

function Test-EndPoint {
  param([string]$Path)
  try {
    $code = (Invoke-WebRequest -UseBasicParsing ($Url.TrimEnd('/') + $Path) -MaximumRedirection 0 -ErrorAction Stop | Select-Object -ExpandProperty StatusCode)
    Write-Host "$Path -> $code"
  } catch {
    Write-Host "$Path -> ERROR"
  }
}

"Running smoke checks for $Url"
Test-EndPoint '/'
Test-EndPoint '/health'
Test-EndPoint '/admin/login'
Test-EndPoint '/api/analytics'