# HelpChain Documentation

HelpChain is a digital coordination infrastructure for structured social, municipal, associative and professional support workflows.

This page is the canonical navigation and authority map for HelpChain documentation.

## Authority statuses

- **CURRENT / SOURCE OF TRUTH — CURRENT IMPLEMENTATION** — documentation verified against current repository behavior. Application code, route guards, scripts, workflow YAML, `render.yaml`, pytest configuration and focused tests remain definitive if a conflict appears.
- **CURRENT / SOURCE OF TRUTH — GOVERNANCE CONTRACT** — canonical rules that new work must follow. This status does not imply that every rule is already implemented or that all legacy behavior has been removed.
- **SUPPORTING** — useful current documentation, but not the primary authority for the subject.
- **NEEDS VALIDATION** — useful material containing statements that may be stale, incomplete, aspirational or contradicted by stronger evidence.
- **LEGACY / INACTIVE** — historical or superseded guidance that must not be followed for current implementation or operations.

This map governs documentation authority. It does not replace executable evidence for actual runtime behavior.

Git cannot prove live Render settings, branch protection, deployed environment variables, the identity of the live Neon database, S3 lifecycle or retention settings, or successful real-world restore readiness.

## Five-minute reading path

1. Start with the root [README](../README.md) for the product, operational model, repository-defined production topology, security, setup and CI summary.
2. Read the [Canonical Operational Spine](architecture/canonical-operational-spine.md) as the governance contract for `Request → Case → Assignment`.
3. Read [System Architecture](02-architecture/system-architecture.md) and the [Tenant Model](02-architecture/tenant-model.md).
4. Read the [Auth and Access Model](06-auth-and-access-model.md) and [RBAC Matrix](06-security/rbac-matrix.md). Route guards and focused tests remain definitive for implemented authorization.
5. Use the verified `scripts/dev.ps1 bootstrap` and `scripts/dev.ps1 run` commands in [Local Development](07-devops/local-development.md), but do not rely on its unverified fallback entrypoint.
6. Use the current workflow YAML and `pytest.ini` for actual test, lint, migration and security-scan behavior.
7. Use `render.yaml` and `scripts/render_start.sh` for repository-defined deployment behavior. The [Restore Runbook](08-runbooks/restore-runbook.md) is coherent but remains unproven until a successful non-production restore and verification of live provider state.

## Current sources of truth

### Current implementation

- [System Architecture](02-architecture/system-architecture.md) — current repository-defined application and production architecture; not proof of live provider state.
- [Tenant Model](02-architecture/tenant-model.md) — current structure boundary and platform-global invariant, verified against repository implementation.
- [Adaptive Module Contract](02-architecture/adaptive-module-contract.md) — explains module-gated route availability, the intentional `404` versus `403` distinction, and the fixture rules for `cases` and `professionals`.
- [Auth and Access Model](06-auth-and-access-model.md) — current login, account, MFA, role and session behavior.
- [RBAC Matrix](06-security/rbac-matrix.md) — current role and tenant-scope behavior; route guards and tests remain definitive.

### Governance and canonical contracts

- [Canonical Operational Spine](architecture/canonical-operational-spine.md) — canonical `Request → Case → Assignment` direction and compatibility boundaries.
- [Request Status Model](03-request-domain/request-status-model.md) — canonical status vocabulary and legacy normalization; acknowledges current implementation debt.
- [Request Lifecycle Engine](03-request-domain/request-lifecycle-engine.md) — canonical transition rules; does not prove complete enforcement across every write path.
- [Request Admin Action Audit](03-request-domain/request-admin-action-audit.md) — required audit behavior; explicitly acknowledges implementation gaps.
- [Request Query and Reporting Rules](03-request-domain/request-query-and-reporting-rules.md) — canonical query and reporting semantics; implementation coverage must be verified in code and tests.
- [Security Policy](../SECURITY.md) — security policy and private vulnerability-reporting contract.

## Supporting documentation

### Overview

- [Product Overview](00-overview/product-overview.md)
- [HelpChain Overview — French](00-overview/HelpChain_Overview_FR.md)
- [HelpChain Overview — English](00-overview/HelpChain_Overview_EN.md)

### Admin operations

- [Admin Panel Manual](04-admin-operations/admin-panel-manual.md)
- [Admin v3 Operational Upgrade](04-admin-operations/admin-v3-operational-upgrade.md)

### Security and quality

- [Secret Safety](06-security/secret-safety.md)
- [Volunteers Nearby Privacy](06-security/volunteers-nearby-privacy.md)
- [Frontend Security](09-quality/frontend-security.md)
- [UX Rules](09-quality/ux-rules.md)
- [Accessibility Checklist](09-quality/a11y-checklist.md)
- [Visual Regression Baseline](09-quality/visual-regression-baseline.md)

### Operations

- [Health and Sanity](08-runbooks/health-and-sanity.md)
- [Notification Jobs Runbook](08-runbooks/notification-jobs-runbook.md)
- [Stability Lockdown Checklist](08-runbooks/stability-lockdown-checklist.md)

## Executable and configuration authority

Use these files to establish current repository behavior:

- application code and route guards — actual request, authentication, authorization and tenant enforcement;
- `render.yaml` and `scripts/render_start.sh` — repository-defined deployment, health, migration and startup behavior;
- `scripts/dev.ps1` — supported local wrapper commands;
- `.github/workflows/ci.yml` — changed-Python-file lint and the blocking integrity smoke gate; full pytest is advisory while its job uses `continue-on-error: true`;
- `.github/workflows/migrations.yml` — path-triggered migration safety guard;
- `.github/workflows/security-scans.yml` — Bandit and pip-audit baseline findings are temporarily non-blocking, while scanner, configuration and report failures remain blocking;
- `pytest.ini` and focused tests — test discovery, markers and verified behavioral coverage.

Repository configuration describes intended repository behavior. It does not prove live provider configuration or external operational readiness.

## Needs validation

Do not use these documents as sole implementation or operational authority:

- [Documentation Status](00-overview/documentation-status.md) — an older registry whose classifications predate current auth, tenant, Render, CI and security-scan evidence. This `docs/README.md` is now the documentation authority map.
- [Data Model](02-architecture/data-model.md) — mixes implemented entities with a target architecture that is explicitly not fully implemented.
- [Request API Contract](03-request-domain/request-api-contract.md) — useful governance material, but route and role claims require verification against current implementation.
- [Request Permission Model](03-request-domain/request-permission-model.md) — contains obsolete `admin → superadmin` normalization and conflicts with the current auth model.
- [Access and Endpoints](06-security/access-and-endpoints.md) — contains obsolete login and role-normalization statements.
- [Production Data Safety](06-security/production-data-safety.md) — documents a coherent repository backup design, but live Neon identity, S3 state, retention and monitoring require external verification.
- [Local Development](07-devops/local-development.md) — use its verified `scripts/dev.ps1 bootstrap` and `run` commands, but do not rely on the unverified fallback entrypoint.
- [CI/CD Policy](07-devops/ci-cd.md) — its all-blocking claim does not match the current advisory full-pytest job or security-baseline semantics.
- [Restore Runbook](08-runbooks/restore-runbook.md) — the repository-defined procedure is coherent, but actual recovery readiness requires a successful non-production restore and verification of live Render, Neon, environment and S3 state.
- [Production Deployment Checklist](../PRODUCTION_DEPLOYMENT_CHECKLIST.md) — combines useful Render and security checks with obsolete Vercel instructions and externally unverifiable assumptions.

## Legacy / inactive

These documents describe superseded or incomplete workflows and must not guide current work:

- [Deployment](07-devops/deployment.md) — treats `vercel.json` as the deployment source of truth; current repository deployment is Render-based.
- [Preview Health](07-devops/preview-health.md) — Vercel preview-specific guidance.
- [Local Development Runbook](07-devops/local-development-runbook.md) — incomplete legacy `help.ps1` instructions.
- [Root Local Runbook](../RUNBOOK.md) — machine-specific legacy launcher, database paths, health endpoint and duplicate-login guidance.

Migration documents are transition records, not proof of current runtime state:

- [Intervenant Migration Plan](02-architecture/intervenant-migration-plan.md)
- [Intervenant Cutover Plan](02-architecture/intervenant-cutover-plan.md)

## Strategic documents

- [Founder operating playbook](founder-operating-playbook.md)
- [First 10 paying clients plan](first-10-paying-clients-plan.md)
- [First 2000 EUR MRR war plan](first-2000-eur-mrr-war-plan.md)
- [Founder daily execution system](founder-daily-execution-system.md)
- [Founder war room dashboard](founder-war-room-dashboard.md)

## Operating principle

Documentation must remain practical, readable and close to executable repository evidence.

For implementation and operations:

- distinguish current implementation evidence from governance contracts;
- do not infer complete implementation from a canonical target or policy;
- do not follow legacy deployment or local-startup instructions;
- verify sensitive authorization claims against route guards and focused regression tests;
- verify live deployment, database, backup and retention state in the relevant provider before an operational action;
- update this map whenever a document’s authority changes.
