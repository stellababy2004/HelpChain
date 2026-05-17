# Restore Runbook (S3 Production Backup)

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current production environment, storage platform, and restore process before using this document for an actual recovery event.

## 1) Find the correct backup file

Use the latest valid object under `postgres/`, if that remains the active backup location:

```bash
aws s3 ls s3://$S3_BUCKET/postgres/ --recursive | sort
```

Select a backup set with all 3 files:
- `helpchain_prod_<timestamp>.sql.gz`
- `helpchain_prod_<timestamp>.sql.gz.sha256`
- `helpchain_prod_<timestamp>.sql.gz.manifest.json`

Download:

```bash
aws s3 cp s3://$S3_BUCKET/postgres/<FILE>.sql.gz .
aws s3 cp s3://$S3_BUCKET/postgres/<FILE>.sql.gz.sha256 .
aws s3 cp s3://$S3_BUCKET/postgres/<FILE>.sql.gz.manifest.json .
```

## 2) Verify checksum and manifest

Validate integrity before any restore:

```bash
sha256sum -c <FILE>.sql.gz.sha256
cat <FILE>.sql.gz.manifest.json
```

Preferred repository validator:

```bash
python scripts/validate_backup_set.py \
  --backup <FILE>.sql.gz \
  --checksum <FILE>.sql.gz.sha256 \
  --manifest <FILE>.sql.gz.manifest.json \
  --expected-repository <owner>/<repo>
```

Check:
- checksum status is `OK`
- manifest `backup_file` matches the downloaded file
- manifest timestamp is the expected restore point
- validator reports `backup integrity status: OK`

This confirms file integrity and basic SQL-gzip readability. It does not prove
that the dump has been restored successfully.

## 3) Restore in staging/local validation first

Never restore directly to production as a first step.

```bash
gunzip -c <FILE>.sql.gz | psql "$STAGING_DATABASE_URL"
```

Create the target staging/local validation database first, then run restore only
against that isolated database. Do not point `STAGING_DATABASE_URL` at production.

## 4) Validate restore success

Minimum checks after restore:
- DB connection works
- key tables are present (`requests`, `admin_users`)
- basic row counts are non-zero/expected
- app health endpoint returns `200`
- admin operational pages open without DB errors

Example SQL checks:

```sql
SELECT COUNT(*) FROM requests;
SELECT COUNT(*) FROM admin_users;
SELECT COUNT(*) FROM structures;
```

Example shell check:

```bash
psql "$STAGING_DATABASE_URL" -c "SELECT COUNT(*) FROM requests;"
psql "$STAGING_DATABASE_URL" -c "SELECT COUNT(*) FROM admin_users;"
```

Record the restore validation date, backup filename, row counts, and operator
name in the incident or operational log.

## 5) What NOT to do

- Do not overwrite production before staging validation.
- Do not skip checksum validation.
- Do not restore from partial backup (missing `.sha256` or `.manifest.json`).
- Do not run schema-changing commands during emergency restore unless explicitly planned.
- Do not delete existing production backups before validation is complete.

## 6) Retention note

- Daily backups are the current expected model.
- Target retention is documented as 30 days on the `postgres/` prefix.
- Workflow fallback is documented as keeping the newest 30 backup sets.

## 7) Safe restore validation checklist (non-production)

- Validate backup integrity first (checksum + manifest consistency).
- Confirm gzip/SQL readability with `scripts/validate_backup_set.py`.
- Restore only to staging/local validation DB.
- Verify:
  - `SELECT COUNT(*) FROM requests;`
  - `SELECT COUNT(*) FROM admin_users;`
  - `SELECT COUNT(*) FROM structures;`
  - application health endpoint returns `200`
- If validation fails, stop and investigate backup integrity/migration state before any production action.

## 8) Production restore decision gate

Before production restore, explicitly confirm:
- the selected backup is the intended recovery point
- staging/local restore has completed successfully
- the current production database has been snapshotted or otherwise preserved
- Render deployment environment variables still point to the intended Neon DB
- stakeholders understand the expected data loss window

If no staging/local restore has been run for the selected backup, restore
readiness is unproven.
