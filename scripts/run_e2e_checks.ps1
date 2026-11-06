param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$BaseTemp = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:HELPCHAIN_TESTING = "1"
$env:HC_ENV = "test"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Output "NOT TESTED: Python interpreter not found: $Python"
    exit 2
}

$groups = @(
    @{ Name = "A-D request-to-case lifecycle"; Tests = @("tests/test_master_e2e_operational.py", "tests/test_request_flow_smoke.py") },
    @{ Name = "B priority/SLA/history/notifications"; Tests = @("tests/test_request_sla_engine.py", "tests/test_admin_audit_trail.py", "tests/test_admin_notification_pipeline_counts.py") },
    @{ Name = "C roles/tenant/CSRF/IDOR"; Tests = @("tests/test_auth_master_e2e.py", "tests/test_auth_access_invariants.py", "tests/test_case_tenant_consistency.py", "tests/test_admin_rbac_security_pass.py") },
    @{ Name = "D referral/reject/close"; Tests = @("tests/test_full_request_flow_html.py", "tests/test_referral_audit_regressions.py", "tests/test_admin_partner_referrals.py") }
)

$failed = 0
$notTested = 0
$skipped = 0
Write-Output "HelpChain local E2E checks (no production server)"

foreach ($group in $groups) {
    $missing = @($group.Tests | Where-Object { -not (Test-Path -LiteralPath $_) })
    if ($missing.Count -gt 0) {
        Write-Output "NOT TESTED: $($group.Name) - missing: $($missing -join ', ')"
        $notTested++
        continue
    }

    $args = @("-m", "pytest", "-q", "-p", "no:cacheprovider") + $group.Tests
    if ($BaseTemp) { $args += @("--basetemp", $BaseTemp) }
    Write-Output "RUNNING: $($group.Name)"
    $output = (& $Python @args 2>&1 | Out-String)
    Write-Output $output.TrimEnd()
    $code = $LASTEXITCODE
    if ($code -eq 0 -and $output -match "\b\d+ skipped\b") {
        Write-Output "SKIPPED: $($group.Name)"
        $skipped++
    } elseif ($code -eq 0) {
        Write-Output "PASS: $($group.Name)"
    } else {
        Write-Output "FAIL: $($group.Name) (exit $code)"
        $failed++
    }
}

if ($failed -gt 0) {
    Write-Output "SUMMARY: FAIL (${failed} group(s)); SKIPPED=$skipped; NOT TESTED=$notTested"
    exit 1
}
if ($notTested -gt 0) {
    Write-Output "SUMMARY: NOT TESTED ($notTested group(s)); SKIPPED=$skipped"
    exit 2
}
Write-Output "SUMMARY: PASS; SKIPPED=$skipped"
exit 0

