# Auth And Access Model

## 1. Purpose
This document is the source of truth for the current HelpChain authentication and authorization model as implemented in the repository.

It covers:
- the canonical admin login surface
- the supported admin roles
- MFA and session behavior
- post-login routing
- request-surface access and structure scoping
- API auth surfaces
- test isolation expectations for auth-focused coverage

This document reflects the current implemented behavior. It does not describe older duplicate login flows or the former `admin -> superadmin` privilege collapse as active behavior.

## 2. Canonical login surface
The canonical web login route for privileged users is:

- `/admin/login`

`/admin/ops/login` remains present only as a legacy compatibility alias:

- it redirects to `/admin/login`
- it is not a separate authentication surface
- it does not execute password-authentication logic directly

Protected admin redirects also resolve to the canonical admin login surface, not to `/admin/ops/login`.

## 3. Account types
The repository distinguishes several account families:

- `AdminUser`: privileged web/admin and API accounts
- structure-scoped admin accounts: `AdminUser` with role `admin` and a structure binding
- global governance accounts: `AdminUser` with role `superadmin` and no structure binding
- operations accounts: `AdminUser` with role `ops`
- read-only admin accounts: `AdminUser` with role `readonly`
- non-admin platform actors such as requester/user, volunteer, and other operational records

This document is concerned with the `AdminUser` access model.

## 4. Role model
The canonical admin roles are:

- `superadmin`: platform-wide governance
- `admin`: structure-level administration
- `ops`: operations-only access
- `readonly`: read-only access

Legacy role normalization is intentionally narrow:

- `super_admin` normalizes to `superadmin`
- `super-admin` normalizes to `superadmin`

`admin` remains `admin`.

There is no active `admin -> superadmin` normalization or privilege escalation path in the role helpers used by the admin routes.

## 5. Authentication methods
Current privileged authentication methods in the repository are:

- Web admin login at `/admin/login` using username-or-email plus password
- Web re-auth at `/admin/re-auth` for fresh-auth-sensitive admin actions
- Web MFA setup and verification via the existing TOTP flow and backup codes
- API login at `/api/auth/login` using JSON username plus password
- API refresh at `/api/auth/refresh`
- API logout at `/api/auth/logout`

The admin web flow is session-based. The API flow is token-based.

The repository also still contains legacy email-2FA compatibility on the web login path when enabled by configuration. The canonical login route remains `/admin/login`.

## 6. MFA policy
Current implemented MFA policy is:

- `superadmin`: required
- `admin`: required
- `ops`: recommended and non-blocking when not enrolled
- `readonly`: optional and non-blocking when not enrolled

Implementation notes:

- the current MFA implementation uses the existing TOTP setup and verification flow
- backup-code verification remains part of the same MFA path
- privileged roles that require MFA do not continue into the normal admin surface until MFA setup or verification is satisfied
- users who already have MFA configured continue through MFA verification before full admin access

For `ops` and `readonly`, lack of MFA enrollment does not block login. If those roles already have MFA configured, the existing verification flow still applies.

## 7. Post-login routing
Current post-login routing is role-aware and uses the following implemented mapping:

- `superadmin` -> `/admin/roles`
- `admin` -> `/admin/pilotage`
- `ops` -> `/admin/operator`
- `readonly` -> `/admin/operator`

This mapping documents the currently implemented landing behavior in the repository.

The `readonly` role currently shares the same landing route as `ops`. That is the implemented behavior and should be treated as the current source of truth unless changed in code.

## 8. Authorization model
Authorization is role-based and route-specific.

Current high-level rules:

- `superadmin` is the governance/global role
- `admin` is a structure-level administrative role
- `ops` is an operational role, not a governance role
- `readonly` is read-only and does not imply governance authority

Request-surface rules currently implemented:

- `/admin/requests` is available to `superadmin` and `admin`
- `/admin/requests/<id>` is available to `superadmin` and `admin`
- structure scoping applies to request queries
- destructive request actions remain tighter than request list/details access

Governance/security rules currently implemented:

- `/admin/security` is a governance/global surface
- it is not a plain structure-admin page
- it should be understood as a global admin/superadmin operational-security page

Routes that remain explicitly tighter than request list/details access are intentionally not broadened by this model unless their own route logic says otherwise.

## 9. Tenant/structure scoping
HelpChain uses tenant/structure-aware access for admin request surfaces.

Current structure-scoping behavior:

- global `superadmin` can operate platform-wide
- structure-level `admin` is scoped through the request query layer
- structure-scoped request list/details access is preserved through the request-scoping helpers rather than by duplicating separate route trees

This means:

- a structure-level `admin` can access request list/details in scope
- that same role does not become a platform-wide governance role

## 10. Onboarding
The repository includes organization onboarding that creates a structure together with an admin account.

Current onboarding behavior:

- onboarding creates an `AdminUser` with role `admin`
- that account is structure-bound
- onboarding emails users the canonical login URL `/admin/login`

This aligns onboarding with the canonical login surface and the structure-level `admin` role.

## 11. Offboarding
Offboarding is handled through account lifecycle and role/access control, not through a separate alternate login model.

Current repo-grounded behavior:

- privileged access is tied to `AdminUser`
- API login explicitly checks that the `AdminUser` is active
- web/admin route access remains governed by authenticated admin session state plus route role checks

This document treats offboarding as removal or deactivation of privileged `AdminUser` access and the corresponding loss of route eligibility.

## 12. Temporary password policy
The repository includes onboarding flows that can send a temporary password to a newly created admin account.

Current behavior:

- structure onboarding may send a welcome email containing a temporary password provided during onboarding
- onboarding points the new admin to `/admin/login`

This document does not define a separate universal password-reset policy beyond the implemented onboarding behavior and the current login/re-auth/MFA flow.

## 13. Session rules
The admin web surface is session-based.

Current implemented session rules include:

- Flask-Login-backed admin session handling
- protected admin redirects targeting the canonical `/admin/login` surface
- no remember-me persistence in the normal admin login completion flow
- admin idle-session tracking
- fresh-auth enforcement for sensitive actions via `/admin/re-auth`
- MFA session verification state with a bounded validity window

Admin session access therefore depends on:

- a valid authenticated admin session
- the route’s role gate
- fresh-auth requirements where applicable
- MFA session validity for users subject to MFA enforcement

## 14. API auth rules
Current API auth surfaces are:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Current conservative rules:

- API login authenticates `AdminUser` accounts using username and password
- API login explicitly requires the user to be active
- refresh uses stored refresh-token state and token rotation
- logout revokes the presented refresh token

This document treats API auth as part of the same `AdminUser` role universe as the web admin surface. It does not claim route-by-route API authorization semantics beyond what is explicitly implemented in the API layer.

## 15. Legacy compatibility rules
The active legacy-compatibility rules are:

- `/admin/ops/login` remains only as a redirect to `/admin/login`
- legacy role aliases `super_admin` and `super-admin` normalize to `superadmin`
- `admin` does not normalize to `superadmin`

Older duplicate-login or privilege-collapse behavior is not current behavior and should not be used as an implementation reference.

## 16. Security invariants
The implemented security invariants for admin access are:

- `/admin/login` is the single real web login surface
- `/admin/ops/login` is not a second live authentication surface
- `admin` and `superadmin` are separate roles with separate meaning
- `superadmin` and `admin` require MFA before full admin access
- `ops` and `readonly` do not receive governance privileges through landing or normalization
- `/admin/security` remains a governance/global surface
- request list/details access for `admin` is structure-scoped, not platform-wide
- tighter/destructive request actions are not broadly widened by the request list/details access model

## 17. Test requirements
Auth-focused and admin-focused tests must run against an isolated test database, not against the runtime SQLite database under `instance/app.db`.

Current implemented test hygiene:

- root tests use a dedicated isolated SQLite file under `.tmp/`
- test app startup does not run the runtime DB integrity check path when `TESTING=True`

Auth-focused tests must align with the implemented model:

- `/admin/login` is canonical
- `/admin/ops/login` is redirect-only
- `admin` is not `superadmin`
- global-governance tests use `superadmin`
- structure-scoped request tests use `admin` where appropriate
- privileged-route tests must satisfy the current MFA gate when they intend to reach the route body
