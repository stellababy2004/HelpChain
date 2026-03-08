# Restore Runbook (S3 Production Backup)

## 1) Find the correct backup file

Use the latest valid object under `postgres/`:

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

Check:
- checksum status is `OK`
- manifest `backup_file` matches the downloaded file
- manifest timestamp is the expected restore point

## 3) Restore in staging/local validation first

Never restore directly to production as first step.

```bash
gunzip -c <FILE>.sql.gz | psql "$STAGING_DATABASE_URL"
```

Run restore only against isolated staging/local validation DB.

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
```

## 5) What NOT to do

- Do not overwrite production before staging validation.
- Do not skip checksum validation.
- Do not restore from partial backup (missing `.sha256` or `.manifest.json`).
- Do not run schema-changing commands during emergency restore unless explicitly planned.
- Do not delete existing production backups before validation is complete.

## 6) Retention note

- Daily backups are expected.
- Target retention: 30 days on S3 lifecycle (`postgres/` prefix).
- Workflow fallback also keeps the newest 30 backup sets.

## 7) Safe restore validation checklist (non-production)

- Validate backup integrity first (checksum + manifest consistency).
- Restore only to staging/local validation DB.
- Verify:
  - `SELECT COUNT(*) FROM requests;`
  - `SELECT COUNT(*) FROM admin_users;`
  - application health endpoint returns `200`
- If validation fails, stop and investigate backup integrity/migration state before any production action.
