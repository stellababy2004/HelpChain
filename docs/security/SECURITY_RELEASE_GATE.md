# HelpChain — Security Release Gate

Status: **DRAFT — not enforced**  
Owner approval: required before enabling merge restrictions or production deployment.  
Created: 2026-11-10

## Purpose

Prevent new, actionable production security findings from silently accumulating, while safely triaging existing scanning debt. Scanning results alone are not proof of exploitability or compromise.

## Existing controls (verified on main, 2026-11-10)

| Control | Workflow | Triggers | Current limitation |
| --- | --- | --- | --- |
| CodeQL | `.github/workflows/codeql-analysis.yml` | main push, PR, weekly | SARIF findings are not themselves an enforced merge gate |
| Trivy FS/IaC | `.github/workflows/trivy-scan.yml` | main push, PR, daily | SARIF findings require triage and baseline comparison |
| Bandit | `.github/workflows/security-scans.yml` | main push, PR | Existing findings explicitly non-blocking |
| pip-audit | `.github/workflows/security-scans.yml` | main push, PR | Only audits root `requirements.txt`, not `api/requirements.txt`; findings explicitly non-blocking |
| Gitleaks | `.github/workflows/secret-scan.yml` | push, PR | Verify actual job outcome and scope |
| CI lint/tests | `.github/workflows/ci.yml` | main push, PR | Changed-file lint with legacy baseline |
| Full quality | `.github/workflows/quality-gate-full.yml` | PR, manual | Must verify required-check settings |

## Security triage policy

1. Preserve all scanner results; never disable scanners or auto-dismiss alerts to obtain a green build.
2. Distinguish newly introduced findings from pre-existing findings. Maintain a versioned, dated baseline with alert IDs, tool, rule, file, severity, reachability, triage decision and rationale. Do not assume all 1,370 open alerts are unique exploitable vulnerabilities.
3. **New confirmed production Critical/High**: block release pending fix, or documented exception with compensating controls, expiry and explicit owner approval.
4. **Existing production Critical/High**: prioritize triage and remediation. A baseline is not a blanket waiver.
5. **Unclassified severity**: evaluate rule, security impact and reachability; do not silently treat as Low.
6. Test-only, local/demo-only, and false-positive classifications require evidence; recheck for production equivalents.
7. Changes to auth, RBAC, tenant isolation, referrals, audit logging and sensitive data paths require targeted regression tests.
8. Changes to dependencies require an installation/compatibility test of the actual deployment dependency path, including `api/requirements.txt` where applicable.

## Proposed automated gate — acceptance criteria

- Run on PRs against main and support manual execution.
- Collect scan statuses, artifacts and available security findings with least-privilege read access. Avoid dependence on unavailable API permissions; fail clearly on missing evidence, never report a false PASS.
- Audit every deployed dependency manifest, not just the root requirements file; validate installability and resolve conflicting pins.
- Compare new findings against a documented baseline and publish a human-readable summary (new/known, severity, production reachability, scan completeness).
- Mark gate FAIL for new, confirmed production Critical/High findings and for required scanner execution failures; unknown/partial scans must be explicitly reported as INCOMPLETE, not PASS.
- Keep existing backlog separately tracked and progressively reduce it.
- No automatic alert dismissal, remediation, production migrations, backups, or Render deploys.
- Enforce required PR checks through repository rulesets/branch protection **only after** confirming permission, plan support and successful test runs.

## Release decision checklist

- [ ] Required scanners completed; missing reports explained
- [ ] Dependency manifests and deployment graph verified
- [ ] No unresolved new confirmed production Critical/High findings
- [ ] Existing Critical/High findings reviewed with owners and remediation plan
- [ ] Relevant regression tests and CI passed
- [ ] Exception record exists for any accepted risk (scope, reason, mitigations, expiry, approver)
- [ ] Human approval recorded before merge and separately before manual production deploy
- [ ] Post-deploy smoke, logs and health checked using fictional data

## Baseline snapshot (Codex report, unverified independently)

2026-11-10: 1,370 open alerts: CodeQL 1,349; Trivy 13; Bandit 8. High 48; Medium 263; Low 1; unclassified 1,058. Local patch on `security-code-scanning-audit-20261110` for #4240 and #3307/#3304; 7 targeted tests passed, complete scan not obtained; review remains conditional. No merge/deploy authorized.

## Next implementation steps

1. Verify current rulesets/branch protection and scanner permissions.
2. Confirm runtime manifest(s) and test Werkzeug 3.1.9 compatibility.
3. Design the baseline format and non-destructive reporting job.
4. Test on an isolated PR without introducing production changes.
5. Enable enforcement only after owner approval.

Notion management register: https://app.notion.com/p/414041b224078131a392fea2fbcfb60e
