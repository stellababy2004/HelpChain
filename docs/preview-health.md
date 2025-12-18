# Preview Health Checks (Vercel)

- Canonical health endpoint for previews: `/health`.
- `/api/_health` may return 404 if Vercel Project-level Routes override repo `vercel.json`.
- The smoke script (`scripts/smoke.ps1`) treats `/api/_health = 404` as a soft warning when `/health = 200`.
- If you want `/api/_health` to be 200 as well, add the following UI route in Vercel Project Settings → Routing (place it before other rules):

  - `^/api/_health$` → `api/_health.js`

## Why

- Some teams maintain Project-level Routes in the Vercel UI for debugging or experiments. Those can take precedence over repo routes.
- Using `/health` avoids surprises and keeps preview diagnostics consistent even when UI overrides are active.

## Related files

- Repo routes: `vercel.json`
- Handlers: `api/_health.js`, `api/analytics.js`, `api/root.js`, `api/favicon.js`
- Smoke checks: `scripts/smoke.ps1`
