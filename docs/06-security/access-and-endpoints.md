# HelpChain Access Model and Endpoints

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against current role and tenant enforcement in code and runtime before using this document for security decisions.

This document is a supporting endpoint inventory. The login, role, and tenant rules identified below as current implementation have been checked against repository code and focused tests. The remaining endpoint matrix still requires route-by-route validation.

HelpChain uses a role-based access model combined with tenant scoping.

Application code, route guards, actor policies, and focused tests remain authoritative for current implementation. See `docs/06-auth-and-access-model.md`, `docs/06-security/rbac-matrix.md`, and `docs/02-architecture/tenant-model.md`.

Two key mechanisms enforce access control:

1. Role-based authorization (AdminUser.role)
2. Tenant isolation via structure_id

## 1. Local Access

These local entry points are implementation-dependent and should be validated against the current developer workflow in `docs/07-devops/local-development.md`.

Local development access depends on the entrypoint used.

`run.py`
- Host: `0.0.0.0`
- Port: `PORT` env var (default `5000`)
- Example: `http://127.0.0.1:5000`
- LAN (when bound to `0.0.0.0`): `http://<LAN-IP>:5000`

`start_server.py`
- Host: `HOST` env var (default `127.0.0.1`)
- Port: `PORT` env var (default `5005`)
- Example: `http://127.0.0.1:5005`
- LAN: only if `HOST=0.0.0.0`, e.g. `http://<LAN-IP>:5005`

`start_waitress.py`
- Host: `127.0.0.1`
- Port: `5000`
- Example: `http://127.0.0.1:5000`

## 2. Login Entrypoints

### Current implementation

- `/admin/login`
  - canonical web login for `AdminUser` accounts;
  - accepts username-or-email plus password;
  - continues through MFA when required;
  - creates the completed admin session only after the applicable authentication steps succeed.

### Legacy compatibility

- `/admin/ops/login`
  - remains registered for compatibility;
  - GET and POST redirect to `/admin/login`;
  - does not provide a separate authentication flow.

Volunteer login:
- `/volunteer_login`

The `admin`, `superadmin`, `ops`, and `readonly` administrative roles use the `AdminUser` model.

## 3. Role Model

### Current implementation

Roles are stored on `AdminUser.role`. Current canonical normalization is:

- `admin` remains `admin`;
- `superadmin`, `super_admin`, and `super-admin` normalize to `superadmin`;
- `ops` remains `ops`;
- `readonly` and `read-only` normalize to `readonly`.

`admin` and `superadmin` are distinct roles. A structure-level `admin` does not become a platform `superadmin`.

Tenant scoping uses `AdminUser.structure_id`:

- **platform-global superadmin**: active authenticated actor, canonical role `superadmin`, and `structure_id is NULL`;
- **structure-attached superadmin**: role `superadmin` with a structure; remains tenant-scoped;
- **structure admin**: role `admin` with a structure; tenant-scoped;
- **operator**: role `ops`; tenant-scoped to the attached structure;
- **readonly**: role `readonly`; access only where explicitly allowed and within tenant scope.

Platform-global status does not by itself grant every route. The relevant route guard or policy must allow the operation, and web routes may additionally require MFA or fresh authentication.

## 4. Navigation Layers

The UI is split into four layers:

1. Public
2. Platform Admin
3. Structure Admin
4. Operations

Visibility rules:
- Platform-global superadmin: Public + Platform Admin + Operations where permitted
- Structure admin: Public + Structure Admin + Operations
- Operator: Public + Operations
- Anonymous: Public

## 5. Main Endpoint Groups

Endpoint groupings below are operationally useful, but they are not a substitute for verifying route guards in code.

Public:
- `/`
- `/comment-ca-marche`
- `/professionnels`
- `/pour-les-structures`
- `/contact`

Admin Platform (platform-global superadmin where enforced by the current route policy):
- `/admin/structures`
- `/admin/roles`
- `/admin/sla`
- `/admin/audit`
- `/admin/security`

Structure Admin (structure admin + platform-global superadmin, subject to route policy):
- `/admin/requests`
- `/admin/requests/new`
- `/admin/requests/<id>`
- `/admin/structures/<id>` (own structure for structure admins)

Operations (operator + structure admin + global admin):
- `/ops/`
- `/ops/workspace`
- `/ops/cases`
- `/ops/notifications`

Operational requests (documented here as currently public):
- `/requests`
- `/requests/dashboard`
- `/requests/operations`

## 6. Access Matrix

Treat this matrix as a working reference, not as a formal access-control proof. Validate current behavior in code and runtime before using it for audit or compliance work.

Legend:
- ✔ allowed
- redirect → login
- 403/404 denied

| Route | Anonymous | Operator | Structure Admin | Platform-global Superadmin |
| --- | --- | --- | --- | --- |
| `/` | ✔ | ✔ | ✔ | ✔ |
| `/comment-ca-marche` | ✔ | ✔ | ✔ | ✔ |
| `/professionnels` | ✔ | ✔ | ✔ | ✔ |
| `/pour-les-structures` | ✔ | ✔ | ✔ | ✔ |
| `/contact` | ✔ | ✔ | ✔ | ✔ |
| `/admin/structures` | 404 | 404 | 403/404 | ✔ |
| `/admin/roles` | redirect | 403/404 | 403/404 | ✔ |
| `/admin/sla` | 404 | 404 | 403/404 | ✔ |
| `/admin/audit` | redirect | 403/404 | 403/404 | ✔ |
| `/admin/security` | redirect | 403/404 | 403/404 | ✔ |
| `/admin/requests` | redirect | 404 | ✔ | ✔ |
| `/admin/requests/new` | redirect | 404 | ✔ | ✔ |
| `/admin/requests/<id>` | redirect | 404 | ✔ | ✔ |
| `/admin/structures/<id>` | 404 | 404 | ✔ (own only) | ✔ |
| `/ops/` | 404 | ✔ | ✔ | ✔ |
| `/ops/workspace` | 404 | ✔ | ✔ | ✔ |
| `/ops/cases` | 404 | ✔ | ✔ | ✔ |
| `/ops/notifications` | 404 | ✔ | ✔ | ✔ |
| `/requests` | ✔ | ✔ | ✔ | ✔ |
| `/requests/dashboard` | ✔ | ✔ | ✔ | ✔ |
| `/requests/operations` | ✔ | ✔ | ✔ | ✔ |

Notes:
- The matrix is a working inventory, not proof of every route. Verify the actual decorators, policies, and object-scope checks before making a security decision.
- The admin session gate and protected admin redirects use the canonical `/admin/login` surface.
- Individual decorators may deny with 403 or hide a resource with 404.
- Structure-admin access to `/admin/structures/<id>` is restricted to their own structure.

## 7. Security Notes

- **Platform-global invariant**: the actor must resolve from an active `AdminUser`, be authenticated, have canonical role `superadmin`, and have no attached `structure_id`.
- **Tenant scoping**: non-global administrative actors remain constrained to their attached structure. A structure-attached `superadmin` is not platform-global.
- **Role normalization**: `admin` remains distinct; only `super_admin` and `super-admin` are legacy aliases for `superadmin`.
- **Route protection**: authentication, role checks, tenant filtering, object-level checks, and MFA/fresh-auth requirements are separate layers. No single role label guarantees access to every endpoint.
- **Operational requests endpoints** (`/requests/*`) currently have no auth guard in `social_requests.py` and are publicly accessible.

### Direct URL protection

UI navigation hides platform routes from structure admins and operators,
but route-level authorization is also enforced to prevent direct URL access.

## 10. Tenant Model

HelpChain is multi-tenant at the structure level.

Requests, operations and dashboards are scoped by:

structure_id

Platform-global superadmins may bypass tenant filtering only where the relevant policy permits it.
Structure-bound admins, ops users, and structure-attached superadmins remain restricted to their own structure.

## 8. Local Test Accounts

Roles map to `AdminUser` fields:

Example mapping:
- Platform-global superadmin: `role=superadmin`, `structure_id=NULL`
- Structure-attached superadmin: `role=superadmin`, `structure_id=<id>`
- Structure admin: `role=admin`, `structure_id=<id>`
- Operator: `role=ops`, `structure_id=<id>`
- Readonly: `role=readonly`, `structure_id=<id>`

Password management scripts:
- `init_admin.py`: initialize an admin user
- `reset_admin_pw.py`: reset admin password
- `reset_admin_password_simple.py`: reset admin password (simple flow)

These scripts use the real password hashing mechanism; do not set passwords manually in the database.

## 9. QA Test Checklist

Platform-global superadmin tests:
- Access `/admin/structures`, `/admin/roles`, `/admin/sla`, `/admin/audit`, `/admin/security`
- Access `/admin/structures/<any>` dashboard

Structure admin tests:
- Access `/admin/requests`, `/admin/requests/new`
- Access `/admin/structures/<own>` only
- Denied on `/admin/structures` list and platform routes

Operator tests:
- Access `/ops/*`
- Denied on `/admin/*`
