# Health & Sanity Endpoints

## Status
- Reviewed: 2026-04
- Status: Active
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current runtime and deployed route set before relying on endpoint details in operational checks.

## `/health` (public, machine-friendly)

Minimal JSON health response:

- `status` (`ok` / `error`)
- `app` (`ok`)
- `db` (`ok` / `error`)
- `time` (UTC ISO timestamp)
- `environment` (safe environment label)
- `version` (if `APP_VERSION`, `GIT_SHA`, or `HEROKU_SLUG_COMMIT` is set)

DB check is expected to be lightweight.
If DB check fails, the endpoint is expected to return HTTP `503`.

## `/admin/sanity` (admin-only, human-friendly)

Expected operational overview page for admins:

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
