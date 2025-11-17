# HelpChain – Security Policy (Full Version)

Last updated: 2025-11-15

This full policy document describes the technical and organizational security controls implemented for HelpChain. It is intended for users, volunteers, administrators, security reviewers, and auditors who need detailed insight into the platform’s defensive posture.

## 1. Scope

Covered areas: authentication, password lifecycle, session/token handling, application-layer defenses (OWASP Top 10), dependency vulnerability management, monitoring, incident response, data minimization.

## 2. Password Hashing and Storage

- Algorithm: Argon2id (resistant to GPU/parallel cracking).
- Parameters (subject to future rehash if strengthened): time_cost=3, memory_cost=64MB, parallelism=2, hash_len=32.
- Migration: Legacy PBKDF2 hashes are transparently upgraded to Argon2id upon successful login.
- Plaintext passwords are never stored or logged.
- Passwords are not redistributed by email.

## 3. Password Complexity Policy

A password must:

- Be at least 10 characters.
- Contain at least one lowercase letter.
- Contain at least one uppercase letter.
- Contain at least one digit.
- Not appear on the common password blacklist (see Section 4).

## 4. Common Password Blacklist

A curated top 10k list of frequently used passwords is enforced. Any match is rejected with a generic error. The list can be expanded; entries are normalized to lowercase for matching.

## 5. Two-Factor Authentication (2FA) & Backup Codes

- TOTP (time-based one-time passwords) supported for administrators and sensitive roles.
- Backup codes: generated once, shown initially, then masked. Each code is single-use.
- Storage: salted + peppered SHA256 hash. Pepper is an environment variable (NEVER committed).
- Usage is logged in the audit log with a partial hash prefix only.

## 6. Failed Login Lockout

- After N (e.g., 5) consecutive failed attempts, the account is temporarily locked (e.g., 10 minutes).
- A successful login after lock expiration resets counters.
- Goal: mitigate brute-force and credential stuffing.

## 7. CSRF Protection

- All state-changing POST forms embed a CSRF token.
- AJAX requests send `X-CSRFToken` header.
- Missing/invalid token yields HTTP 400 and a dedicated error page.

## 8. HTTP Security Headers

Implemented headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy-Report-Only: default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'`
  (CSP enforced in Report-Only mode initially to allow tuning.)

## 9. Secure Cookies

- `HttpOnly`, `Secure`, `SameSite=Lax` for session-related cookies.
- Sensitive tokens are not placed in localStorage where possible (reduces XSS impact).

## 10. JWT and Session Handling

- Strict validation of `iss`, `aud`, `exp`.
- Short-lived access tokens; planned refresh-token rotation for improved session hygiene.
- Tokens are validated server-side; compromised tokens have limited useful lifetime.

## 11. Rate Limiting

- Critical API endpoints are protected by per-IP sliding window limits.
- Response headers communicate remaining quota.
- Goal: throttle brute-force, enumeration, and denial-of-service attempts at application layer.

## 12. Audit Logging

- Sensitive events logged: backup code usage, elevated role changes, admin authentications.
- No raw secrets stored (only truncated hash prefixes or safe metadata).
- Logs are stored securely and periodically reviewed.

## 13. Dependency & Vulnerability Management

- Continuous scanning via `pip-audit` (produces SARIF) and `safety` (JSON → SARIF conversion).
- Dependabot weekly updates (Python packages + GitHub Actions).
- Specialized monitoring script for dependency upgrade feasibility (e.g., HTTP stack packages).
- Security PRs require review before merge.

## 14. Vulnerability Handling Workflow

1. Discovery (automated scanner or user report).
2. Validation & impact assessment.
3. Prioritization (Critical → High → Medium → Low).
4. Remediation (upgrade package / patch code / configuration change).
5. Testing (functional + regression).
6. Deployment and documentation (CHANGELOG / security notes).

## 15. Reporting Security Issues

Users or volunteers can report suspected security issues through official in-app contact or published email channels. Please include reproduction steps, expected vs. actual behavior, timestamp, and environment details.

## 16. OWASP Top 10 Coverage (High-Level Mapping)

| Category                          | Mitigations                                                      |
| --------------------------------- | ---------------------------------------------------------------- |
| Injection                         | ORM parameterization (SQLAlchemy); avoidance of dynamic raw SQL. |
| Broken Auth                       | Argon2id hashing; lockout; 2FA; audit logs.                      |
| Sensitive Data Exposure           | Secure hashing; planned TLS hardening; minimal data retention.   |
| XML External Entities             | No untrusted XML parsing employed.                               |
| Broken Access Control             | Role checks at API endpoints; explicit authorization gates.      |
| Security Misconfiguration         | Automated scans; security headers; secrets via env.              |
| XSS                               | CSP (Report-Only initial); template escaping.                    |
| Insecure Deserialization          | No untrusted pickle/object deserialization.                      |
| Using Vulnerable Components       | pip-audit, safety, Dependabot.                                   |
| Insufficient Logging & Monitoring | Audit logs; planned Sentry integration.                          |

## 17. Roles & Access Control

- Principle of least privilege for admin versus regular users.
- Role elevation/change operations are logged.
- Periodic review of active admin accounts (automation planned).

## 18. Infrastructure Security (General Guidance)

- Mandatory TLS (HTTPS everywhere).
- Optional IP allow listing for admin interfaces.
- Secret rotation (pepper, API keys) at least annually or upon incident.

## 19. Session Expiration & Revocation

- Short token TTL limits attack window.
- Planned: explicit refresh token revocation on suspicious activity.

## 20. Incident Response (Condensed)

1. Detection (alerts, anomaly in logs, user report).
2. Containment (temporary blocks, key rotation).
3. Analysis (scope, root cause).
4. Remediation (code/config updates, patches).
5. Communication (notify affected users if personal data impacted).
6. Post-mortem (document lessons, preventive measures).

## 21. Data Minimization & Privacy

- Only necessary user attributes are collected.
- Planned cleanup of stale/inactive accounts.
- No sharing of personal data with third parties without legitimate basis.

## 22. Log Access

- Restricted to authorized administrators.
- Sensitive data excluded (no plaintext passwords, full backup codes, tokens).

## 23. Roadmap for Future Enhancements

- Optional password rotation policy.
- Full CSP enforcement (after resource audit).
- Sentry / centralized monitoring integration.
- Automated stale admin account detection.
- Additional defenses against credential stuffing (IP/device heuristics).

## 24. Limitations & Transparency

- Some measures (e.g., advanced encryption at rest specifics) depend on deployment environment and may vary.
- Certain configuration (TLS cipher suites, WAF rules) intentionally not publicized to reduce reconnaissance value.

## 25. Contact

For security-related inquiries or to report a vulnerability use the in-app contact channel or the designated security email (if published).

---

If inconsistencies are found between the live application behavior and this document, the operational settings take precedence; please report discrepancies for correction.
