$ErrorActionPreference='Stop'
gh workflow run prebuild-and-deploy.yml --repo stellababy2004/HelpChain.bg --ref chore/vercel-ignore-extra
Start-Sleep -Seconds 3
$jsonText = gh run list --repo stellababy2004/HelpChain.bg --workflow prebuild-and-deploy.yml --limit 20 --json id,headBranch
if (-not $jsonText) { Write-Output 'No runs returned'; exit 1 }
$json = $jsonText | ConvertFrom-Json
$match = $json | Where-Object { $_.headBranch -eq 'chore/vercel-ignore-extra' } | Select-Object -First 1
if (-not $match) { Write-Output 'Could not find run for branch'; exit 1 }
$id = $match.id
Write-Output "Found run id: $id"
while ((gh run view $id --repo stellababy2004/HelpChain.bg --json status -q .status) -eq 'in_progress') { Start-Sleep -Seconds 5 }
gh run view $id --repo stellababy2004/HelpChain.bg --log
