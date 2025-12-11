param(
  [long]$run = 20133520571,
  [string]$repo = 'stellababy2004/HelpChain.bg',
  [int]$timeoutMinutes = 10
)
$end = (Get-Date).AddMinutes($timeoutMinutes)
while((Get-Date) -lt $end) {
  $metaJson = gh run view $run --repo $repo --json status,conclusion 2>$null
  if (-not $metaJson) { Write-Output "no metadata yet"; Start-Sleep -Seconds 5; continue }
  $meta = $metaJson | ConvertFrom-Json
  $concl = if ($meta.conclusion) { $meta.conclusion } else { 'null' }
  Write-Output ("{0} {1}" -f $meta.status, $concl)
  if ($meta.status -eq 'completed') { break }
  Start-Sleep -Seconds 5
}
gh run view $run --repo $repo --log > "run$run.log"
Write-Output "Saved run$run.log"