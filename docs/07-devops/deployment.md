# Routing and Deployment Policy

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current deployment platform and repository routing configuration before using this document as release guidance.

Source of truth: `vercel.json` in the repository root.

## Canonical Routing Policy

- explicit-only endpoints
- `404` by default for unknown routes
- controlled introduction of new routes
- deterministic routing behavior

## Operational Guidance

- Keep routing policy aligned with `vercel.json`.
- Reflect material routing decisions in active documentation when they affect deployment behavior.
- When opening a pull request that changes routing, document the operational impact clearly.

## Stability Checklist

- `/api/_health` returns the expected result for the current deployment context
- `/health` returns `200`
- unknown routes return `404`

## Policy Intent

The objective is to move routing behavior from implicit convention to explicit contract so deployment behavior remains stable over time.
