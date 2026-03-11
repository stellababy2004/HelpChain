# Health & Sanity Endpoints

## `/health` (public, machine-friendly)

Minimal JSON health response:

- `status` (`ok` / `error`)
- `app` (`ok`)
- `db` (`ok` / `error`)
- `time` (UTC ISO timestamp)
- `environment` (safe environment label)
- `version` (if `APP_VERSION`, `GIT_SHA`, or `HEROKU_SLUG_COMMIT` is set)

DB check is lightweight (`SELECT 1`).
If DB check fails, endpoint returns HTTP `503`.

## `/admin/sanity` (admin-only, human-friendly)

Operational overview page for admins:

- application runtime metadata (environment, version, generated time)
- DB connectivity state
- requests table availability + safe aggregate counts
- critical route registration checklist
- Sentry configured flag (boolean only)

## Safety rules

The endpoints intentionally do **not** expose:

- DB URIs
- credentials, tokens, DSNs
- stack traces
- request-level personal data
