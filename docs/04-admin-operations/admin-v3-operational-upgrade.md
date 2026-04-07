# Admin Panel v3 Operational Upgrade

## Scope

- Release type: UX and operational maturity upgrade
- Surface: admin requests dashboard
- Backend impact: none
- Schema changes: none
- Migration required: no

## Intent

Admin Panel v3 improves the requests dashboard so administrators can identify urgent work faster, filter operational queues more reliably, and share a consistent view of current workload.

## Key Changes

Structural improvements:

- unified filtering across status and actionable state
- URL-persistent dashboard state
- clickable KPI cards
- row-level navigation with keyboard support

Operational signals:

- actionable-only toggle with counter
- live mini-panel for unassigned and in-progress work
- priority-aware row highlighting
- volunteer response chips such as `CAN_HELP` and `CANT_HELP`
- clearer urgency cues from low to urgent

Interaction improvements:

- copy-link flow compatible with stricter CSP
- lightweight feedback notifications
- clearer hover and selection affordances
- better keyboard accessibility

## Expected Operational Impact

Compared with the previous table-driven view, the upgraded dashboard is intended to reduce scanning time, make urgent requests visible sooner, and improve routing speed for operators handling a large queue.

## Risk Profile

Risk remains low because the upgrade does not change the backend contract, data model, or request-domain governance rules.

Monitor:

- filtering performance on large datasets
- priority normalization and display consistency

## Rollback Scope

If rollback is required, the relevant surface is limited to the admin requests frontend layer, including:

- `static/js/admin-requests-filters.js`
- `static/js/admin-requests-rowclick.js`
- `static/js/admin-requests-actionable-mark.js`
- `static/js/admin-copy-link.js`
- `static/css/pages/admin-ui.css`
- `templates/admin/requests.html`

Rollback returns the dashboard to the earlier list-oriented view without changing backend behavior.
