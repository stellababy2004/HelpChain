# HelpChain Documentation

## What HelpChain Is

HelpChain is a France-first institutional coordination platform for managing requests, assignments, operational follow-up, and controlled access across structures. It is designed for public-interest and institutional environments that require traceability, role-based access, and operational clarity.

## Documentation Principles

- Documentation is organized by domain so operational, product, architectural, and governance material remain easy to navigate.
- English is the primary documentation language for the active documentation tree.
- Archived material is preserved for historical reference only and must not be treated as the current source of truth.
- Canonical governance documents for the Request domain remain authoritative and should be read before changing workflow behavior.

## Documentation Map

- `00-overview/` Institutional and executive-level platform overviews.
- `01-product/` Product-facing documentation and positioning material when maintained.
- `02-architecture/` Canonical structural model, migration plans, and target-state architecture.
- `03-request-domain/` Governance baselines for the Request lifecycle, permissions, API contract, and reporting rules.
- `04-admin-operations/` Practical guidance for the admin workspace and operational workflows.
- `05-api/` API-specific documentation that does not belong to request governance or security.
- `06-security/` Access control, data protection, privacy boundaries, and secret-handling guidance.
- `07-devops/` Deployment, local development, CI/CD, and runtime integration notes.
- `08-runbooks/` Operational procedures for health checks, restores, and recurring jobs.
- `09-quality/` Quality standards, UX guardrails, accessibility checks, and regression baselines.
- `archive/` Historical, temporary, superseded, or investigative material preserved for context.

## Start Here If You Are...

### Developer

Start with:

- `07-devops/local-development.md`
- `02-architecture/data-model.md`
- `03-request-domain/request-api-contract.md`
- `03-request-domain/request-lifecycle-engine.md`

### Operator / Admin

Start with:

- `04-admin-operations/admin-panel-manual.md`
- `08-runbooks/health-and-sanity.md`
- `08-runbooks/mini-runbook.md`
- `08-runbooks/restore-runbook.md`

### Product / Stakeholder Reader

Start with:

- `00-overview/HelpChain_Overview_EN.md`
- `02-architecture/data-model.md`
- `04-admin-operations/admin-v3-operational-upgrade.md`

## Canonical Documents

The following documents define the active source of truth for request governance and runtime operations:

- `03-request-domain/request-status-model.md`
- `03-request-domain/request-admin-action-audit.md`
- `03-request-domain/request-permission-model.md`
- `03-request-domain/request-api-contract.md`
- `03-request-domain/request-lifecycle-engine.md`
- `03-request-domain/request-query-and-reporting-rules.md`
- `02-architecture/data-model.md`
- `06-security/access-and-endpoints.md`
- `07-devops/deployment.md`
- `06-security/production-data-safety.md`
- `08-runbooks/restore-runbook.md`
- `08-runbooks/health-and-sanity.md`

## Archive

Archived documents are retained for institutional memory, incident review, migration history, or past audits. They may contain outdated assumptions, machine-specific details, or time-bound conclusions and must not be used as active operational guidance.
