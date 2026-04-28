# HelpChain Auth & Route Inventory

## Official access routes

| Purpose | Route | Status |
|---|---|---|
| Admin login | `/admin/login` | KEEP |
| Admin dashboard | `/admin/home` | KEEP |
| Requests | `/admin/requests` | KEEP |
| Cases | `/admin/cases` | KEEP |
| Intervenants | `/admin/intervenants` | KEEP |
| Revenue | `/admin/revenue` | KEEP |
| Security | `/admin/security` | KEEP |
| Structures | `/admin/structures` | KEEP |
| Ops workspace | `/ops/workspace` | KEEP |
| Ops login | `/admin/ops/login` | KEEP |

## Keep for now

| Route | Reason |
|---|---|
| `/admin/2fa` | MFA legacy/compatibility flow |
| `/admin/mfa/setup` | MFA setup |
| `/admin/mfa/verify` | MFA verification |
| `/admin/mfa/backup-codes` | MFA backup codes |
| `/auth/magic/<token>` | Magic link flow |
| `/api/auth/*` | API authentication |
| `/logout` | General logout |
| `/requester/logout` | Requester logout |
| `/volunteer/logout` | Volunteer POST logout |

## Cleanup candidates

| Route | Issue | Priority |
|---|---|---|
| `/admin/login` | Registered twice: legacy + current endpoint | High |
| `/admin/proposal/<id>` | Registered multiple times from proposal experiments | High |
| `/admin_dashboard` | Legacy admin dashboard route | Medium |
| `/admin_analytics` | Legacy analytics route | Medium |
| `/admin_volunteers` | Legacy volunteers route | Medium |
| `/admin/admin_volunteers` | Compatibility route | Low |
| `/volunteer_login` | Legacy-style URL | Medium |
| `/volunteer_logout` | Legacy logout route | Medium |
| `/admin/professionnels/leads` | Naming duplicate with professional leads | Low |
| `/admin/pro-access` | Older professional access flow candidate | Review |

## Cleanup strategy

1. Do not remove routes without tests.
2. Clean proposal routes first.
3. Clean duplicated admin login second.
4. Clean volunteer legacy routes last.
5. Keep MFA and API routes untouched until separately audited.

## Current risk

The application works, but route naming has accumulated legacy aliases and duplicate routes.
The risk is not immediate breakage; the risk is future confusion, wrong links, and unstable maintenance.
