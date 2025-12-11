$conflicts = git diff --name-only --diff-filter=U
foreach ($f in $conflicts) {
    if ($f.Trim() -ne '') {
        Write-Output "Resolving $f"
        git checkout --theirs -- $f
        git add $f
    }
}
Write-Output 'Done resolving.'
