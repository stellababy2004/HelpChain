# Canonical migration path

Chosen canonical migration tree: `backend/migrations`

## Why

- The repository currently contains two migration trees (top-level `migrations/` and `backend/migrations/`). That increases the chance of schema ↔ model drift and dialect-specific surprises (we observed Postgres-only DDL executed against SQLite locally).
- Using `backend/migrations` as the single source-of-truth keeps backend code and migrations colocated and simplifies CI and developer workflows.

## What this document covers

- Rationale for choosing `backend/migrations` as canonical.
- Safe consolidation plan (how to move files if desired).
- Local developer commands (recreate DB, stamp head) and CI guidance.

## Quick local commands

Option A — (dev, data can be discarded): recreate local SQLite DB and run migrations

PowerShell (from repo root):

```powershell
Remove-Item -Force .\instance\volunteers.db
python .\run_backend.py --init-db --seed-admin
```

Option B — (preserve local data): stamp DB as migrated without running migrations

PowerShell:

```powershell
$env:DATABASE_URL = 'sqlite:///./instance/volunteers.db'
python -m alembic -c migrations/alembic.ini stamp head
python .\run_backend.py --seed-admin
```

Note: Use Option B only when you understand the schema differences and want to keep existing data.

## Consolidation plan (safe step-by-step)

If you decide to consolidate `migrations/` → `backend/migrations` do it in a single PR with these steps:

1. Pick a short freeze window and a review owner.
2. Ensure you have a database backup for any production-like DBs.
3. In a feature branch copy (do not delete yet) migration files from `migrations/versions/` into `backend/migrations/versions/`.
   - Keep filenames and `revision`/`down_revision` metadata unchanged.
4. Run the local migration test: set `DATABASE_URL` to a disposable Postgres (or local Docker Postgres) and run `python run_migrations.py` to ensure the chain is valid.
5. If the repository currently uses both trees in different environments, add a short migration note in `README.md` pointing to `backend/migrations`.
6. Once reviewers approve, remove the old `migrations/` tree in a separate commit (or keep it but document it as deprecated). Prefer doing the removal in the same PR only if you validated rollback.

## Checklist for reviewers

- All `revision` and `down_revision` identifiers are intact after the move.
- No duplicate `revision` ids were introduced.
- CI runs migrations against Postgres (see workflow) and passes.

## CI validation recommendation

- Add a CI job that runs migrations against a real Postgres instance (service container) and fails on any migration error. This will catch dialect-specific issues (native ENUM / CREATE TYPE) early.

## Follow-ups

- Remove dev-only helper scripts used during debugging before final PR (e.g., `backend/scripts/*`) unless they are intentionally useful for developers.
- Optionally, add a small `scripts/validate_migrations.py` to run migrations against a temporary Postgres for local testing.

## Questions or changes

If you'd prefer the root `migrations/` tree as canonical, we can flip this doc and update the workflows to point to the other path instead.

--
Document created to make the migration path explicit and reduce future flaky runs.
