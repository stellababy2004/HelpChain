# HelpChain

HelpChain is an operational coordination platform for social-sector organisations, local structures and professional networks. It centralises incoming requests, qualification, assignments and operational history without acting as a public marketplace.

French is the primary product language; translations are available for selected interfaces.

## Canonical Operational Model

The current operational spine is:

```text
Request → Case → Assignment
```

`RequestActivity` and `CaseEvent` provide the associated audit trail and history. `SocialRequest` remains a compatibility flow and is not the canonical model for new work.

See [Canonical Operational Spine](docs/architecture/canonical-operational-spine.md) for lifecycle details.

## Architecture and Production

- Application: Flask, SQLAlchemy and Alembic, with server-rendered Jinja interfaces and supporting JavaScript
- Production entrypoint: `gunicorn run:app`, started by `scripts/render_start.sh`
- Deployment path: GitHub → Render web service and background worker → PostgreSQL
- Local database: SQLite, selected by the local bootstrap tooling
- Production database: PostgreSQL
- Database backups: the repository-defined backup workflow uses the configured Neon PostgreSQL source and stores backup artifacts in AWS S3
- Health endpoints: `/health/live` for Render liveness and `/health` for application health

The repository proves the intended topology and workflow configuration; it cannot prove the live provider resources, environment values or GitHub/Render settings.

Architecture details are in [System Architecture](docs/02-architecture/system-architecture.md), [Tenant Model](docs/02-architecture/tenant-model.md) and the [Restore Runbook](docs/08-runbooks/restore-runbook.md).

## Security Model

- Session authentication protects web and administrative flows.
- JWT authentication is used where API routes require token-based access.
- Administrative MFA uses TOTP and recovery codes.
- RBAC controls capabilities by role.
- Structure scoping provides tenant isolation for operational data.

See [Authentication and Access Model](docs/06-auth-and-access-model.md), [RBAC Matrix](docs/06-security/rbac-matrix.md) and [Security Policy](SECURITY.md). Report vulnerabilities through the private process described in `SECURITY.md`; do not open a public issue for sensitive reports.

## Local Development

The canonical Windows development workflow is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 bootstrap
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 run
```

The bootstrap command prepares the local database, schema and administrator, then runs diagnostics. See [Local Development](docs/07-devops/local-development.md) for prerequisites, environment guidance and additional commands.

## Database Migrations

Use the same application entrypoint and migration directory as production:

```bash
python -m flask --app run:app db upgrade --directory migrations
```

Confirm the target `DATABASE_URL` before running migrations against any non-local database.

## Testing and CI

Run the narrowest relevant tests during development, then broaden validation as appropriate:

```bash
pytest -q path/to/test_file.py
pytest -q tests/test_system_integrity.py
pytest -q
```

The `CI` workflow currently provides:

- blocking Ruff and Black checks for changed Python files on pushes and pull requests;
- a blocking `tests/test_system_integrity.py` smoke gate;
- a full pytest job that is still advisory because the job uses `continue-on-error: true`;
- separate migration-safety coverage;
- Bandit and `pip-audit` baseline reporting where security findings are temporarily non-blocking while scanner or configuration failures remain blocking.

Repository workflow definitions describe expected CI behavior, but branch-protection and other GitHub server-side settings are not visible here.

## Documentation Map

- [Canonical Operational Spine](docs/architecture/canonical-operational-spine.md)
- [System Architecture](docs/02-architecture/system-architecture.md)
- [Tenant Model](docs/02-architecture/tenant-model.md)
- [Authentication and Access Model](docs/06-auth-and-access-model.md)
- [RBAC Matrix](docs/06-security/rbac-matrix.md)
- [Local Development](docs/07-devops/local-development.md)
- [Restore Runbook](docs/08-runbooks/restore-runbook.md)
- [Security Policy](SECURITY.md)
