# HelpChain

<p align="center">
  <strong>Operational coordination infrastructure for social-sector organisations and local public services.</strong>
</p>

<p align="center">
  HelpChain turns incoming requests into structured cases, clear ownership, coordinated follow-up and an auditable operational history — without becoming a public marketplace.
</p>

<p align="center">
  <a href="https://github.com/stellababy2004/HelpChain/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/stellababy2004/HelpChain/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-production-4169E1?logo=postgresql&logoColor=white">
  <img alt="France" src="https://img.shields.io/badge/Primary_market-France-0055A4">
  <img alt="Status" src="https://img.shields.io/badge/Status-Active_development-F59E0B">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Proprietary-informational"></a>
</p>

<p align="center">
  <a href="https://helpchain.live"><strong>Website</strong></a>
  ·
  <a href="README.fr.md">Français</a>
  ·
  <a href="README.bg.md">Български</a>
  ·
  <a href="SECURITY.md">Security</a>
  ·
  <a href="docs/README.md">Documentation</a>
</p>

---

## Why HelpChain?

Social-support work often crosses organisations, teams and territories. Requests arrive through different channels, responsibility changes hands, follow-up is fragmented, and managers struggle to see what is happening without chasing people manually.

HelpChain provides one operational spine:

```text
Public intake / internal request
            ↓
         Request
            ↓
           Case
            ↓
       Assignment
            ↓
 Follow-up & CaseEvent audit trail
```

The goal is simple: **the right request, with the right structure and the right person, with a traceable history of what happened next.**

## Core Capabilities

| Capability | What it does |
| --- | --- |
| **Public intake & routing** | Structures incoming requests and routes supported categories toward configured local services. |
| **Request → Case workflow** | Converts demand into an operational case with ownership and lifecycle tracking. |
| **Assignments** | Connects cases to authorised professionals or operational actors. |
| **Multi-tenant isolation** | Scopes operational data and permissions by structure. |
| **Inter-organisation referrals** | Shares a deliberately limited payload with another structure instead of exposing the source tenant's internal case. |
| **Volunteer workflows** | Supports volunteer profiles, authorised membership and matching flows. |
| **Calendar & follow-up** | Links operational follow-up to requests and cases. |
| **Audit trail** | Uses RequestActivity, CaseEvent and administrative audit mechanisms to preserve operational history. |
| **Website analytics** | Records supported events such as page views, CTA clicks and form submissions. |
| **Internationalisation** | French-first product with multilingual support across selected interfaces. |

> **Current product status:** active development and acceptance testing. Repository capabilities and automated tests do not by themselves mean that HelpChain is declared pilot-ready. Critical cross-role and end-to-end flows are validated before that gate is claimed.

## Designed Around Real Operational Boundaries

HelpChain is not designed as an open marketplace where every user can see every request.

The platform separates:

- citizens or request originators;
- structures and their administrators;
- professionals / intervenants;
- volunteers;
- platform-level administration.

Authorisation is expected to follow explicit identity, role and structure membership. A default structure, an email address, or historical activity must not silently become proof of tenant membership.

## Canonical Operational Model

The current canonical operational spine is:

```text
Request → Case → Assignment
```

`RequestActivity` and `CaseEvent` provide the associated audit trail and history. `SocialRequest` remains a compatibility flow and is not the canonical model for new work.

See [Canonical Operational Spine](docs/architecture/canonical-operational-spine.md) for lifecycle details and [Inter-organisation Referrals](docs/02-architecture/inter-organization-referrals.md) for the controlled cross-structure sharing model.

## Architecture

```text
Browser
  │
  ▼
Flask / Jinja application
  │
  ├── Authentication & RBAC
  ├── Public intake & routing
  ├── Request / Case / Assignment workflows
  ├── Volunteer & professional workflows
  ├── Referrals / calendar / analytics
  │
  ▼
SQLAlchemy + Alembic
  │
  ▼
PostgreSQL (production)
```

### Production topology

- **Application:** Flask, SQLAlchemy, Alembic, Jinja and supporting JavaScript
- **Production entrypoint:** `gunicorn run:app`, started by `scripts/render_start.sh`
- **Deployment path:** GitHub → Render web service / worker → PostgreSQL
- **Local database:** SQLite through local bootstrap tooling
- **Production database:** PostgreSQL
- **Backups:** repository-defined workflow targets the configured Neon PostgreSQL source and AWS S3 backup storage
- **Health:** `/health/live` for liveness and `/health` for application health

The repository proves the intended topology and workflow configuration. It does **not** by itself prove live provider resources, secrets, environment values or external service settings.

More detail: [System Architecture](docs/02-architecture/system-architecture.md) · [Tenant Model](docs/02-architecture/tenant-model.md) · [Restore Runbook](docs/08-runbooks/restore-runbook.md)

## Security Model

Security is part of the product boundary rather than a UI-only concern.

- Session authentication protects web and administrative flows.
- JWT authentication is used where API routes require token-based access.
- Administrative MFA uses TOTP and recovery codes.
- RBAC controls capabilities by role.
- Structure scoping provides tenant isolation for operational data.
- Sensitive cross-structure sharing uses explicit referral boundaries.
- Security-sensitive changes are covered by targeted regression tests.

See [Authentication and Access Model](docs/06-auth-and-access-model.md), [RBAC Matrix](docs/06-security/rbac-matrix.md) and [Security Policy](SECURITY.md).

**Security reports:** please use the private process in `SECURITY.md`; do not open a public issue for a sensitive vulnerability.

## Local Development

Canonical Windows workflow:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 bootstrap
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 run
```

The bootstrap command prepares the local database, schema and administrator, then runs diagnostics.

See [Local Development](docs/07-devops/local-development.md) for prerequisites and environment guidance.

## Database Migrations

Use the same application entrypoint and migration directory as production:

```bash
python -m flask --app run:app db upgrade --directory migrations
```

Always confirm the target `DATABASE_URL` before running migrations against any non-local database.

## Testing & CI

During development, start with the narrowest relevant regression suite and broaden validation when appropriate:

```bash
pytest -q path/to/test_file.py
pytest -q tests/test_system_integrity.py
pytest -q
```

The main **CI** workflow currently runs:

1. **Ruff + Black gate** for changed Python files, while avoiding failure on documented pre-existing Black debt.
2. **Smoke Gate** using `tests/test_system_integrity.py`.
3. **Full pytest suite** after the smoke gate.

A green CI run is necessary, but product readiness additionally requires cross-role, multi-tenant and real end-to-end acceptance testing.

## Acceptance Philosophy

HelpChain uses a stricter readiness rule than “the page loads” or “unit tests pass”.

Critical flows are checked across real roles and boundaries, including:

- public intake → routing → correct structure;
- structure admin ownership and isolation;
- professional assignment and case actions;
- volunteer identity, membership, matching and actions;
- case lifecycle and closed-case immutability;
- inter-organisation referrals;
- calendar and follow-up consistency;
- authentication and identity edge cases;
- negative cross-tenant access attempts;
- idempotency and stale-state scenarios.

This keeps **feature existence**, **automated regression coverage** and **pilot readiness** as three different claims.

## Documentation

| Area | Reference |
| --- | --- |
| Operational model | [Canonical Operational Spine](docs/architecture/canonical-operational-spine.md) |
| Architecture | [System Architecture](docs/02-architecture/system-architecture.md) |
| Tenant isolation | [Tenant Model](docs/02-architecture/tenant-model.md) |
| Referrals | [Inter-organisation Referrals](docs/02-architecture/inter-organization-referrals.md) |
| Authentication | [Authentication and Access Model](docs/06-auth-and-access-model.md) |
| RBAC | [RBAC Matrix](docs/06-security/rbac-matrix.md) |
| Local development | [Local Development](docs/07-devops/local-development.md) |
| Operations | [Restore Runbook](docs/08-runbooks/restore-runbook.md) |
| Security | [Security Policy](SECURITY.md) |

## Project Status

**Stage:** MVP / active development  
**Primary market:** France  
**Product language:** French-first  
**Current engineering focus:** end-to-end acceptance, role/tenant consistency and verified product documentation

HelpChain is being developed toward controlled real-world use. Commercial, pilot and scale claims should be based on verified field evidence rather than repository activity alone.

## License

HelpChain is proprietary software. The source code and associated materials are not open source and may not be copied, modified, distributed, deployed or commercially used without prior written permission. See [LICENSE](LICENSE) for the applicable terms.

---

<p align="center">
  <strong>HelpChain</strong><br>
  Coordination that stays traceable.
</p>
