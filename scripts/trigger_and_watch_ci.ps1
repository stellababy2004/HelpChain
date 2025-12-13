$repo = "stellababy2004/HelpChain.bg"
$workflow = "prebuild-and-deploy.yml"
$ref = "chore/remove-distinfo-and-add-gitleaks"

Write-Output "Dispatching workflow $workflow on $ref to $repo"
$dispatch = gh workflow run $workflow --repo $repo --ref $ref 2>&1
Write-Output $dispatch

Start-Sleep -Seconds 2

for ($i = 0; $i -lt 120; $i++) {
    try {
        $listJson = gh run list --repo $repo --workflow $workflow --limit 1 --json databaseId,status,conclusion 2>$null
        if (-not $listJson) { Start-Sleep -Seconds 5; continue }
        $list = $listJson | ConvertFrom-Json
        if ($list -and $list.Count -gt 0) {
            $r = $list[0]
            Write-Output "Status: $($r.status)  Conclusion: $($r.conclusion)  RunId: $($r.databaseId)"
            if ($r.status -ne 'in_progress' -and $r.status -ne 'queued') { break }
        }
    } catch {
        Write-Output "Error querying runs: $_"
    }
    Start-Sleep -Seconds 10
}

Write-Output "Done watching. Check the run page for details."
