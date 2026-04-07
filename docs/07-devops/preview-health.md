# Preview Health

## Canonical Rule

Use `/health` as the canonical preview health endpoint.

## Notes

- `/api/_health` can return `404` when Vercel project-level routing overrides repository routing.
- The smoke script may treat `/api/_health = 404` as a soft warning when `/health = 200`.
- If a secondary `/api/_health` endpoint is required, keep the corresponding Vercel route ahead of broader routing rules.

## Why This Matters

Preview diagnostics should stay stable even when platform-level routing experiments or overrides exist. Using `/health` avoids ambiguity.

## Related Assets

- `vercel.json`
- `api/_health.js`
- `scripts/smoke.ps1`
