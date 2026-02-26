# Restore Runbook

## A) Bad deploy / migration

1. Check Render logs and the latest deploy.
2. If the issue is DB-related, use Neon Instant Restore / PITR to a timestamp before the deploy.
3. Validate critical checks:
   - `/health` returns `200`
   - `/admin/api/ops-kpis` returns `200`
4. Run a short post-mortem: identify the migration/commit that caused the issue.

## B) Deleted / corrupted data

1. Use Neon PITR to a moment before the deletion/corruption.
2. Verify key tables (for example `requests`, volunteer-related state tables).
3. If needed, restore into an isolated environment/branch for comparison before touching production.

## C) Outage

1. UptimeRobot alert fires -> open Render dashboard.
2. If health checks are failing, rollback the deploy.
3. If DB connections are failing, check Neon status and use PITR if needed.

## S3 SQL backup restore snippet

```bash
aws s3 ls s3://helpchain-backups/prod/ | tail
aws s3 cp s3://helpchain-backups/prod/<FILENAME>.sql.gz .
gunzip -c <FILENAME>.sql.gz | psql "$DATABASE_URL"
```
