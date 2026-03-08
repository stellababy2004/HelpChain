# Production Data Safety (Operational)

## Scope
- Backup/restore safety for Neon Postgres + AWS S3.
- Migration drift visibility (no automatic upgrades).
- Non-production restore validation only.

## Daily backup model
- Workflow: `.github/workflows/db-backup-to-s3.yml`
- Schedule: daily (`02:05 UTC`)
- Backup set per run:
  - `helpchain_prod_<timestamp>.sql.gz`
  - `helpchain_prod_<timestamp>.sql.gz.sha256`
  - `helpchain_prod_<timestamp>.sql.gz.manifest.json`

## Integrity checks
- Workflow: `.github/workflows/db-backup-integrity-check.yml`
- Validates latest S3 backup set:
  - required files exist (`.sql.gz`, `.sha256`, `.manifest.json`)
  - checksum matches file content
  - manifest required fields are present and consistent
- If validation fails, workflow fails.

## Backup audit trail
- Manifest includes operational traceability:
  - `generated_at_utc`
  - `repository`
  - `git_sha`
  - `workflow`, `run_id`, `run_number`
  - `s3_key_backup`, `s3_key_checksum`, `s3_key_manifest`

## Retention
- Target policy: S3 lifecycle retention of 30 days under `postgres/`.
- Workflow fallback also keeps newest 30 backup sets.

## Migration drift visibility
- Local visibility command:
  - `.\.venv\Scripts\python.exe .\scripts\migration_status.py`
- Strict fail-fast mode:
  - `.\.venv\Scripts\python.exe .\scripts\migration_status.py --fail-on-outdated`
- `scripts/dev_doctor.ps1` also reports DB revision/head/status.

## Restore validation flow (non-prod only)
1. Select backup set (all 3 files).
2. Verify checksum + manifest.
3. Restore to staging/local validation DB.
4. Validate:
   - DB connection works
   - key tables exist (`requests`, `admin_users`)
   - row counts readable
   - app health endpoint returns `200`

Use detailed restore steps from `docs/RESTORE_RUNBOOK.md`.

## What NOT to do
- Do not restore directly to production as first step.
- Do not skip checksum/manifest verification.
- Do not run destructive schema operations during emergency restore.
- Do not run automatic migration upgrades in safety checks.
