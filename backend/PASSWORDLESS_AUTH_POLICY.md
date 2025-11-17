# HelpChain Passwordless Authentication Security Policy

_Last updated: 2025-11-15_

## 1. Overview / Преглед

HelpChain is migrating from local password-based authentication to a passwordless model using Microsoft (Entra ID) OpenID Connect (OIDC). This policy documents security objectives, required controls, residual risks, and fallback / recovery mechanisms.
HelpChain преминава от локални пароли към passwordless модел с Microsoft (Entra ID) OpenID Connect (OIDC). Тази политика описва целите за сигурност, контроли, остатъчни рискове и механизми за възстановяване.

## 2. Objectives / Цели

- Reduce password-related attack surface (credential stuffing, weak passwords, phishing)
- Centralize identity lifecycle & MFA enforcement via Microsoft platform
- Preserve secure fallback for break-glass administrative access
- Maintain auditability of identity binding events and login flows
- Provide clear user onboarding and recovery paths

## 3. Scope / Обхват

Covers all interactive user and admin logins to the HelpChain platform (web application) and associated identity data stored in the primary database (SQLite → future RDBMS).

## 4. Architecture Summary / Резюме на архитектурата

- Users initiate login by entering email, then redirect to Microsoft authorization endpoint with PKCE & nonce.
- Authorization Code exchanged for tokens; `id_token` signature verified via JWKS; critical claims checked: `iss`, `aud`, `exp`, `nonce`, `sub`.
- User record binds `ms_oid` (maps to OIDC `sub`) and sets `password_disabled=1`.
- Legacy password hash retained temporarily for rollback; future phase will purge after migration threshold.
- Session established post-validation; no local password accepted once `password_disabled` set.

## 5. Required Security Controls / Задължителни контроли

1. PKCE (S256) on all authorization requests.
2. Nonce per authorization request; single-use, short TTL.
3. JWKS retrieval with caching + integrity validation (HTTPS, JSON schema minimal checks).
4. Claim validation: issuer matches tenant `.../{tenant}/v2.0`, audience == configured client_id.
5. Expiration (`exp`) and time-based claims enforced.
6. Replay prevention: nonce consumed exactly once.
7. Secure session cookie (Secure, HttpOnly, SameSite=Lax or Strict in production).
8. Audit logging for: bind event, failed validation (issuer/audience/nonce), admin break-glass usage.
9. Minimum TLS version 1.2 enforced at reverse proxy / hosting layer.

## 6. Data Elements / Данни

| Field                | Purpose                                 | Retention                    | Notes                    |
| -------------------- | --------------------------------------- | ---------------------------- | ------------------------ |
| `ms_oid`             | External stable identifier (OIDC `sub`) | Permanent                    | Unique index enforced    |
| `password_disabled`  | Flag disallowing legacy local password  | Permanent                    | Set upon successful bind |
| Legacy password hash | Transitional rollback                   | Max 90 days post-migration   | Purge schedule required  |
| Nonce values         | Replay prevention                       | Ephemeral (<5 min)           | In-memory only           |
| Audit logs           | Forensics & compliance                  | 1–2 years (policy to define) | Exportable               |

## 7. Fallback & Recovery / Резервни механизми

- Break-glass admin account (single) retains local password + enforced 2FA (TOTP) until passwordless verified stable.
- Recovery path if Microsoft unavailable: temporary enablement of break-glass only; normal users must wait (no insecure downgrade).
- Manual re-bind procedure: admin can clear `ms_oid` and re-run login to re-establish association (requires elevated approval & audit entry).

## 8. Deprecation Plan for Local Passwords / План за премахване на пароли

Phase 1 (Complete): Add columns (`ms_oid`, `password_disabled`).
Phase 2 (Active): Bind users during first Microsoft login; disable local password immediately.
Phase 3 (Scheduled): After ≥95% accounts bound OR date threshold, purge legacy hashes (anonymize or set to irreversible random). Create backup encrypted snapshot before purge.
Phase 4 (Audit): Verify no code paths still depend on password; remove complexity checks in UI; update documentation.

## 9. Residual Risks / Остатъчни рискове

| Risk                    | Description                                              | Mitigation                                                         | Status                 |
| ----------------------- | -------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------- |
| IdP compromise          | If Microsoft tenant compromised attacker may sign tokens | Maintain anomaly detection; consider token issuer allowlist alerts | Ongoing                |
| Token replay (id_token) | Potential reuse within validity window                   | Nonce + short session TTL for sensitive ops                        | Implemented (nonce)    |
| JWKS key rotation lag   | Cached keys stale during rotation                        | 1h TTL + forced refresh on signature failure                       | Implemented            |
| Break-glass abuse       | Local account misuse for privilege                       | Strict audit & 2FA, restricted knowledge                           | In progress            |
| Email mismatch binding  | Wrong email captured before redirect                     | Re-validate email from `id_token` if available                     | Implemented (fallback) |

## 10. Monitoring & Audit / Мониторинг

Events to log:

- Successful Microsoft bind (user_id, ms_oid, timestamp)
- Failed claim validation (reason)
- Break-glass login attempts (success/failure)
- Purge operation of legacy password hashes (count, checksum)

## 11. Compliance & Privacy / Съответствие

- `ms_oid` treated as pseudonymous identifier; avoid exposing externally.
- Email considered personal data; storage complies with GDPR: used strictly for account binding & notifications.
- Provide user data export & account deletion processes (future enhancement).

## 12. Implementation Gaps / Пропуски

- Audit log persistence (pending)
- Scheduled purge task (pending)
- Formal retention periods for audit data (needs policy decision)
- Documentation for end-user recovery flows (pending)

## 13. Action Items / Действия

| ID  | Item                                           | Priority | Owner        | Target     |
| --- | ---------------------------------------------- | -------- | ------------ | ---------- |
| A1  | Implement structured audit logging module      | High     | Security Eng | 2025-11-30 |
| A2  | Build purge script for legacy hashes           | High     | Backend Eng  | 2025-12-15 |
| A3  | Configure secure cookie flags in production    | High     | DevOps       | 2025-11-25 |
| A4  | Document user-facing recovery FAQ              | Medium   | Product      | 2025-12-01 |
| A5  | Add monitoring alert on unusual bind frequency | Medium   | Security Eng | 2025-12-05 |

## 14. Glossary / Речник

- OIDC: OpenID Connect authentication protocol over OAuth2.
- PKCE: Proof Key for Code Exchange – mitigates code interception.
- JWKS: JSON Web Key Set – published signing keys for ID tokens.
- Break-glass account: Emergency access with stricter controls.

## 15. Change Log / История на промени

- 2025-11-15: Initial passwordless policy drafted.
