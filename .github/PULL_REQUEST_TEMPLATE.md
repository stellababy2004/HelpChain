## Summary
- Short description of the change

## Motivation
- Why is this change needed?

## Changes
- Key points:
  - ...

## Preview Health (Vercel)
- Canonical health endpoint for previews: `/health`.
- `/api/_health` may be 404 if Project-level Routes in Vercel override repo `vercel.json`.
- Our smoke script treats `/api/_health = 404` as a soft warning when `/health = 200`.
- To force `/api/_health = 200`, add UI route (Project Settings → Routing): `^/api/_health$ → api/_health.js` before other rules.

## Checklist
- [ ] Tests pass locally (`pytest`)
- [ ] Updated docs/README where applicable
- [ ] Smoke passed on preview deployment(s)
- [ ] Security considerations reviewed
