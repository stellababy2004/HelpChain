# Documentation Status

## Canonical Documents

- `docs/03-request-domain/request-status-model.md`
- `docs/03-request-domain/request-admin-action-audit.md`
- `docs/03-request-domain/request-permission-model.md`
- `docs/03-request-domain/request-lifecycle-engine.md`
- `docs/03-request-domain/request-query-and-reporting-rules.md`
- `docs/02-architecture/data-model.md`

## Active Operational Documents

- `docs/04-admin-operations/admin-panel-manual.md`
- `docs/07-devops/local-development.md`
- `docs/08-runbooks/health-and-sanity.md`
- `docs/08-runbooks/mini-runbook.md`
- `docs/09-quality/a11y-checklist.md`

## Migration Documents

- `docs/02-architecture/intervenant-migration-plan.md`
- `docs/02-architecture/intervenant-cutover-plan.md`

## Documents Requiring Validation

- `docs/06-security/access-and-endpoints.md` - Access rules and endpoint behavior should be validated against current route guards and tenant enforcement.
- `docs/06-security/production-data-safety.md` - Backup, retention, and infrastructure assumptions should be validated against the current production setup.
- `docs/07-devops/deployment.md` - Deployment guidance should be validated against the current platform and repository routing configuration.
- `docs/07-devops/local-development.md` - Developer workflow should be validated against current local scripts and runtime expectations.
- `docs/08-runbooks/restore-runbook.md` - Restore steps should be validated against the current backup storage and recovery procedure.
- `docs/08-runbooks/health-and-sanity.md` - Endpoint details should be validated against the current deployed runtime.
- `docs/08-runbooks/notification-jobs-runbook.md` - Queue, command, and job-runner assumptions should be validated against the current production implementation.

## Notes

- `Canonical` means current source of truth for a governed domain.
- `Active` means current operational guidance, but not a core governance artifact.
- `Migration` means transition strategy only and not a guarantee of current runtime state.
- `Needs validation` means the document remains useful, but current infrastructure, runtime, or enforcement details should be checked before relying on it operationally.
