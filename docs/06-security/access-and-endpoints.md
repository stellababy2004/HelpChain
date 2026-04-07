# HelpChain Access Model and Endpoints

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against current role and tenant enforcement in code and runtime before using this document for security decisions.

This document describes the current intended HelpChain access model, login entrypoints, and key endpoints based on the documented implementation.

HelpChain uses a role-based access model combined with tenant scoping.

Where route behavior or enforcement is environment-dependent, validate directly against current code and runtime.

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

Current documented login entrypoints:
- `/admin/ops/login`

Legacy admin login:
- `/admin/login`

Volunteer login:
- `/volunteer_login`

Admin, superadmin, operator, readonly all use the same authenticated model: `AdminUser`.

## 3. Role Model

This section describes the intended normalized role model. Validate against current route decorators, normalization logic, and tenant filters before relying on it as a security decision record.

Roles are stored on `AdminUser.role` and normalized in `admin.py`:
- `admin`, `super_admin`, `superadmin` are normalized to **superadmin**
- `ops` is **operator**
- `readonly` is **readonly**

Tenant scoping uses `AdminUser.structure_id`:
- **global_admin**: normalized admin role AND `structure_id is NULL`
- **structure_admin**: normalized admin role AND `structure_id is NOT NULL`
- **operator**: role `ops`
- **readonly**: role `readonly`

## 4. Navigation Layers

The UI is split into four layers:

1. Public
2. Platform Admin
3. Structure Admin
4. Operations

Visibility rules:
- Global admin: Public + Platform Admin + Operations
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

Admin Platform (global admin only):
- `/admin/structures`
- `/admin/roles`
- `/admin/sla`
- `/admin/audit`
- `/admin/security`

Structure Admin (structure admin + global admin):
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

| Route | Anonymous | Operator | Structure Admin | Global Admin |
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
- Admin endpoints often use `admin_required` (404 for non-admin) and some use `login_required` (redirects to `/admin/ops/login`).
- Structure-admin access to `/admin/structures/<id>` is restricted to their own structure.

## 7. Security Notes

- **Global vs structure admin enforcement**: Platform-only admin routes require a normalized admin role and `structure_id is NULL`.
- **Tenant scoping**: Admin request queries are filtered by `current_structure_id()` unless the user is global admin.
- **Role normalization**: `admin`, `super_admin`, `superadmin` are treated as `superadmin`.
- **Route protection**: `admin_required` hides admin routes from non-admins (404), `operator_required` restricts ops routes to `ops`, `readonly`, or admins.
- **Operational requests endpoints** (`/requests/*`) currently have no auth guard in `social_requests.py` and are publicly accessible.

### Direct URL protection

UI navigation hides platform routes from structure admins and operators,
but route-level authorization is also enforced to prevent direct URL access.

## 10. Tenant Model

HelpChain is multi-tenant at the structure level.

Requests, operations and dashboards are scoped by:

structure_id

Global admins are expected to bypass tenant filtering.
Structure admins and operators are expected to be restricted to their own structure.

## 8. Local Test Accounts

Roles map to `AdminUser` fields:

Example mapping:
- Global admin: `role=admin|superadmin`, `structure_id=NULL`
- Structure admin: `role=admin`, `structure_id=<id>`
- Operator: `role=ops`, `structure_id=<id>`
- Readonly: `role=readonly`, `structure_id=<id>`

Password management scripts:
- `init_admin.py`: initialize an admin user
- `reset_admin_pw.py`: reset admin password
- `reset_admin_password_simple.py`: reset admin password (simple flow)

These scripts use the real password hashing mechanism; do not set passwords manually in the database.

## 9. QA Test Checklist

Global admin tests:
- Access `/admin/structures`, `/admin/roles`, `/admin/sla`, `/admin/audit`, `/admin/security`
- Access `/admin/structures/<any>` dashboard

Structure admin tests:
- Access `/admin/requests`, `/admin/requests/new`
- Access `/admin/structures/<own>` only
- Denied on `/admin/structures` list and platform routes

Operator tests:
- Access `/ops/*`
- Denied on `/admin/*`
