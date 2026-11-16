# Security findings triage — 2026-11-15

## Scope and immutable baseline

- Repository: `stellababy2004/HelpChain`
- Current `main` inspected: `69991f0e396ce3e993fb889a9fd95614b0e57222`
- Review branch: `security/evidence-based-findings-triage-20261115`
- Evidence collection date: 2026-11-15

This is an evidence register, not an acceptance of alerts. GitHub Code
Scanning was queried directly for open alerts on `main`; scanner artifacts
were not available locally. Dependabot REST access reports that alerts are
disabled. Secret Scanning returned zero open alerts. No production or
environment-secret verification was performed.

## Evidence register

| ID | Scanner | Severity | Finding | Status | Evidence | Action | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MAN-20261115-01 | Source audit | Critical | Unauthenticated `/admin/proposal/<id>` and `/admin/proposal-clean/<id>` disclose professional-lead PII | REMEDIATED — local regression tested | `app.py` direct app routes bypassed `admin_bp` guard; anonymous requests returned 404 after fix | Gate by canonical platform-commercial policy | Maintainer |
| MAN-20261115-02 | Source audit | High | Tenant-scoped bearer admin could receive global volunteer location/contact data | REMEDIATED — local regression tested | `api.py` queried all `Volunteer` rows; model has no `structure_id` | Fail closed to platform-global bearer admin pending membership-backed scope | Maintainer |
| MAN-20261115-03 | Source audit | High | Authenticated user/session could update any volunteer location by ID | REMEDIATED — local regression tested | `api.py` had no ownership check | Require own volunteer session/user record or platform-global bearer admin | Maintainer |
| MAN-20261115-04 | Source audit | High | Password-only `/api/auth/login` minted JWT for roles requiring MFA | REMEDIATED — local regression tested | API route lacked the UI MFA gate | Deny login/refresh until an API MFA protocol exists | Maintainer |
| CSQL-OPEN-20261115 | CodeQL + Bandit | High/Medium/Error | 1,338 open Code Scanning alerts | OPEN — untriaged at alert level | GitHub REST, exact main SHA; CodeQL 1,336 and Bandit 2 | Triage each active security rule and reachable path; no blanket disposition | Security owner |
| DEP-20261115 | Dependabot / pip-audit | Unknown | Dependabot alert inventory unavailable | EVIDENCE UNAVAILABLE | GitHub API: `Dependabot alerts are disabled` (403) | Enable/review Dependabot separately; retain local pip-audit evidence | Repository owner |
| SEC-20261115 | Secret Scanning | None returned | Open secret-scanning alerts | NO OPEN ALERTS RETURNED | GitHub REST query on current main returned `[]` | Do not treat as proof of historical-secret remediation | Security owner |
| GL-PIPE-20261115 | Gitleaks / Trusted Gate | High assurance gap | Secret Scan workflow does not produce required `gitleaks-results.sarif` artifact | CONFIRMED BLOCKER | `.github/workflows/secret-scan.yml` only invokes action; collector requires exact artifact | Restore a pinned, validated report-producing workflow and align collector format before trusted review | Maintainer |
| B104-ADMIN-20261115 | Bandit | Unclassified | `request.remote_addr or "0.0.0.0"` client-IP fallback | FALSE POSITIVE — existing exact disposition | `PR-203-FINDINGS-DISPOSITIONS-2026-11-11.json`: identity `bandit|b104|backend/helpchain_backend/src/routes/admin.py|2423`, digest `sha256:8168a08e75fe76475215886ac7447558e07540a82ea3226f89cb18373813f385`, expiry 2027-11-15 | No change: this triage did not modify `admin.py`, so context is unaffected | Owner-approved |

## Current Code Scanning inventory

The direct GitHub response contains 1,338 open records: CodeQL 1,336 and
Bandit 2. Reported levels are 41 High, 243 Medium, 314 Error, 35 Warning and
705 Note. The High/Error set includes reachable-source candidates such as
`py/polynomial-redos`, `py/url-redirection`, `py/clear-text-logging-sensitive-data`,
`py/path-injection`, `py/reflective-xss`, and many quality-only errors. This
document deliberately does not reclassify those alerts without individual
source-to-sink evidence.

Historical baseline material in repository documentation is preserved only as
historical evidence. It is not substituted for the current-main API result.

## GitHub state checked

PRs 216, 224, 225, 228 and 229 are merged. PR 224 merged as current `main`
at `69991f0e396ce3e993fb889a9fd95614b0e57222`. Its post-merge CodeQL run
`43745427994` completed successfully, but the four observed Trusted Security
Gate runs on that SHA were **skipped**, not PASS. Consequently there is no
current trusted-gate PASS evidence for this baseline.

## Validation performed in this branch

- `pytest tests/test_security_authz_regressions_20261115.py -q`: 12 passed,
  including legitimate platform-global access and legacy proposal-engine
  registration coverage, ID-collision denial, and rejection of a pre-existing
  MFA-required access JWT.
- `pytest` security selection (authz regressions, admin login lockout and
  Security Gate disposition/workflow regressions): 37 collected and completed
  without a reported failure.
- `black --check` on the changed Python files: failed because three pre-existing
  large files are not Black-clean; Black's diff shows unrelated existing
  formatting outside the remediation hunks. The new test file is clean.
- `ruff check` on the changed Python files: failed on pre-existing import-order
  and `UP017` findings in the three existing modules; no blanket ignore added.
- Local CodeQL: unavailable (GitHub Actions evidence used instead).
- Local Gitleaks and Trivy executables: unavailable. `pip-audit` 2.10.1 is
  installed, but its full dependency-resolution execution did not complete
  with a consumable report in this environment; no pass is claimed.
- Dependabot: unavailable because GitHub reports alerts disabled.

## Open risks and pilot-readiness blockers

1. The 1,338 open Code Scanning alerts have not received finding-by-finding
   validation; 41 are reported High.
2. Trusted Security Gate is skipped on current `main`, and its Gitleaks artifact
   contract is unsatisfied by the checked-in Secret Scan workflow.
3. No API MFA ceremony exists. The remediation intentionally denies affected
   API token issuance, so product owners must define a verified API MFA flow
   before restoring that capability.
4. `Volunteer` has no tenant attribute. A membership-backed data model/scope is
   required before tenant admins can safely use the global nearby directory.
5. Dependency inventory is incomplete: CI required audit covers root
   `requirements.txt`; API audit is reporting-only, and Dependabot is disabled.

## Decision

**SECURITY TRIAGE: PARTIAL.** Four source-confirmed vulnerabilities are fixed
and regression-tested locally, but the active alert inventory, scanner
provenance gap, and unavailable evidence prevent a complete triage.

**PILOT SECURITY READINESS: NO-GO.** This is a release decision based on the
open evidence and gate blockers; it is not a statement about production state.
