# PR #224 — Security gate evidence review (2026-11-14)

Status: **OPEN — NOT APPROVED FOR MERGE**. This document records scanner evidence, not a risk acceptance or a disposition.

## Provenance

- PR head: `8ee40c85035261c84cd75b4a344f4dc34e6a4857`
- Scanned PR merge commit: `cf7e8bd66a19acdc77e739aca9a0dd3eb755c746`
- CodeQL workflow run: `43622696298`; 59 reported findings
- Bandit workflow run: `43622696283`; 2 reported findings
- Trivy IaC / repository: 0 findings; pip-audit runtime and API: 0; Gitleaks: 0
- No new confirmed Critical/High findings in the diagnostic summary; this does **not** mean all CodeQL alerts are safe.

## Root cause of red checks

The evaluator in `scripts/security_release_gate.py` recognizes exact dispositions only for three hard-coded finding IDs (`EXPECTED_DISPOSITION_KEYS`). The current scanned evidence includes 59 CodeQL findings and 2 Bandit findings; only the Bandit B104 finding at `extensions.py:23` matches an existing accepted disposition. The remaining 58 are `no exact disposition`, so the evaluator returns `REVIEW REQUIRED` and exits 1. The trusted workflow maps `REVIEW REQUIRED` to a failed PR-head check.

The trusted evaluator checks out the default branch, so modifying only PR #224 cannot safely change its policy. **Do not bypass, suppress, or auto-approve findings to turn checks green.**

## Priority security triage — no disposition granted yet

| Finding | Location in scan | Required verification |
| --- | --- | --- |
| CodeQL `py/url-redirection` | `admin.py:5422` | Verify every tainted `next` value passes `_safe_next_url`, including encoded URLs and role checks |
| CodeQL `py/url-redirection` | `admin.py:6116` | Trace `_finalize_admin_session` and `_next_url_for_admin_user`; add explicit redirect regression cases |
| CodeQL `py/stack-trace-exposure` | `admin.py:8949` | Confirm API error responses never expose exception messages, stack traces, or sensitive details |
| Bandit `B104` | `admin.py:2423` | Confirm `0.0.0.0` is only a fallback client IP, not a listening socket; capture source-context digest |
| CodeQL `py/cyclic-import` | Multiple lines near `admin.py:17173-17189` | Confirm deferred imports do not cause runtime cycles and assess residual CodeQL alerts |

Source locations are from the scanner report; line numbers may move after subsequent commits.

## Follow-up implementation requirements

1. Review each finding against exact scanner output and current source; classify fixed, confirmed risk, or justified false positive **with evidence**.
2. Design a separate policy change that permits reviewed findings without hard-coding exactly three IDs, while preserving strict identity, severity, source-context digest, expiration, duplicate detection, and fail-closed behavior.
3. Add regression tests for forged finding IDs, modified source lines, stale or missing evidence, unknown high-severity findings, and unreviewed findings.
4. Review the policy change independently before merging to `main`; then rerun authoritative trusted evaluation for PR #224.
5. Do not merge PR #224 or deploy to Render until the trusted verdict is successful and the priority findings are resolved.

This review is **not** a security approval for findings other than the two narrowly scoped redirect dispositions below.

## Redirect finding 1: helper fallback

Finding: CodeQL `py/url-redirection` at `backend/helpchain_backend/src/routes/admin.py:5422` (Medium).

`_redirect_to_safe_next` sends a request-derived value to `_safe_next_url` before calling `redirect`. `_safe_next_url` rejects absolute and protocol-relative URLs, backslashes, non-`/admin` or `/ops` paths, and values that fail `is_safe_url`'s HTTP(S) same-origin check. The fallback URL is selected by the calling server route, not by the candidate. The regression suite covers external targets, protocol-relative targets, a backslash bypass, an encoded scheme-like target, and disallowed paths.

Exact source-context digest: `sha256:24c544afa262c65429125368f20ec2d3b7b976e2417e3e3b736e1a960d476923`.

## Redirect finding 2: MFA role authorization

Finding: CodeQL `py/url-redirection` at `backend/helpchain_backend/src/routes/admin.py:6116` (Medium).

`_finalize_admin_session` obtains its target only from `_next_url_for_admin_user`. That function repeats `_safe_next_url` validation, then `_is_next_url_authorized_for_admin_user` permits `/ops` only for a defined admin role and permits `/admin` only when the Flask route resolves and the route's allowed-role decorator includes the authenticated user. Failed validation or authorization selects the caller's server-defined fallback URL. The regression suite verifies rejected external/protocol-relative and unauthorized candidates plus allowed role-specific `/ops` paths.

Exact source-context digest: `sha256:1b2c26bf2424a92da21dd635c52a55ff2848340ef107868b5a310c668e65d54b`.

## Bandit B104: client-IP fallback

Finding: Bandit `B104` at `backend/helpchain_backend/src/routes/admin.py:2423` (unclassified).

`_client_ip` returns the literal only when `request.remote_addr` is absent. Its direct consumers record audit/security metadata and, during login, use the returned string as the `AdminLoginAttempt.ip` key for lockout lookup and logging. Forwarded headers are trusted only through the existing opt-in ProxyFix boundary, which normalizes `request.remote_addr`; raw `X-Forwarded-For` is not read by this helper. There is no socket creation, bind, listen, host configuration, or network exposure on this source-to-sink path. The scanner's hardcoded-bind heuristic therefore does not apply.

The fallback remains an exact string rather than changing the login-attempt/audit contract merely to suppress the scanner. The disposition expires on 2027-11-14 and is bound to the source-context digest below.

Exact source-context digest: `sha256:8168a08e75fe76475215886ac7447558e07540a82ea3226f89cb18373813f385`.

Residual deployment requirement: a deployment that enables `TRUST_PROXY_HEADERS` must restrict ingress to its configured reverse proxy and set the correct ProxyFix hop count. ProxyFix cannot establish network provenance when an application is directly exposed to untrusted clients.
