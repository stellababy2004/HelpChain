# Production Data Safety (Operational)

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current production environment, backup platform, and retention policy before using this document for operational decisions.

## Scope
- Backup/restore safety for Neon Postgres + AWS S3.
- Migration drift visibility (no automatic upgrades).
- Non-production restore validation only.

## Daily backup model

Current expected setup:
- Workflow: `.github/workflows/db-backup-to-s3.yml`
- Schedule: daily (`02:05 UTC`)
- Backup set per run:
  - `helpchain_prod_<timestamp>.sql.gz`
  - `helpchain_prod_<timestamp>.sql.gz.sha256`
  - `helpchain_prod_<timestamp>.sql.gz.manifest.json`

Canonical backup naming is UTC-sortable: `helpchain_prod_YYYYMMDDTHHMMSSZ.sql.gz`.
The `postgres/` S3 prefix is the production backup source of truth.

Legacy/secondary backup workflows may still exist in the repository for manual
or historical use. They are not the primary production recovery source unless
an operator explicitly promotes them during an incident.

## Integrity checks
- Workflow: `.github/workflows/db-backup-integrity-check.yml`
- Validates latest S3 backup set:
  - required files exist (`.sql.gz`, `.sha256`, `.manifest.json`)
  - checksum matches file content
  - manifest required fields are present and consistent
  - gzip payload is readable and looks like a plain PostgreSQL SQL dump
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
- This repository cannot prove the live S3 lifecycle rule. Treat retention as
  unverified until the bucket policy/lifecycle configuration is checked in AWS.

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

Use detailed restore steps from `docs/08-runbooks/restore-runbook.md`.

## Monitoring expectations
- GitHub Actions must be watched for `DB Backup to S3 (Neon Postgres)` and
  `DB Backup Integrity Check` failures.
- UptimeRobot should monitor `/health`, not admin-only pages.
- `/health` is intentionally shallow: it confirms app boot and DB connectivity,
  but it does not prove backup freshness or successful restore.
- Backup freshness is currently inferred from GitHub Actions/S3 state, not from
  the public health endpoint.

## Known resilience gaps
- A full restore into staging/local has not been proven by this repository alone.
- Duplicate historical backup workflows can confuse operators unless the
  canonical workflow above is treated as source of truth.
- S3 retention/lifecycle policy is an external AWS setting and must be verified
  outside Git.
- Failed backup visibility depends on GitHub Actions notifications or manual
  checks unless external alerting is configured.

## What NOT to do
- Do not restore directly to production as first step.
- Do not skip checksum/manifest verification.
- Do not run destructive schema operations during emergency restore.
- Do not run automatic migration upgrades in safety checks.
