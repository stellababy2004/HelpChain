# Admin Panel v3.0 - Operational Layer
**Release type:** UX / Operational Maturity Upgrade  
**Scope:** Admin Dashboard (Requests view)  
**Backend impact:** None  
**Schema changes:** None  
**Migration required:** No  

### Product Intent
This release aims to reduce cognitive load for administrators and enable faster
operational decision-making in high-volume environments.

### 1. Summary
Admin Panel v3 transforms the requests dashboard from a static list into an operational command center.

Focus:
- Faster decision-making
- Clear prioritization
- Actionable filtering
- Real-time situational awareness

Scope:
- No backend changes
- No schema changes
- UX + operational intelligence layer only

### 2. What Changed
Structural:
- Unified filtering engine (`status + actionable`)
- URL-persistent state (`?tab=...&action=1`)
- Clickable KPI cards
- Row-level navigation (mouse + keyboard)

Operational Signals:
- Action-only toggle with dynamic counter
- Live mini-panel (`Unassigned / In Progress / Available volunteers`)
- Actionable row indicator (priority-aware accent)
- `CAN_HELP / CANT_HELP` chips visualization
- Priority-based visual escalation (`LOW -> URGENT`)

Micro UX:
- Copy-link with CSP-safe flow
- Toast notifications
- Tick micro-feedback
- Hover affordance
- Keyboard accessibility

### 3. Operational Impact
Before:
- Admin scans manually
- No clear urgency layer
- Filtering conflicts
- No shareable state

After:
- Instant actionable overview
- Urgency visible in < 3 seconds
- Direct link to filtered operational state
- Reduced cognitive load
- Faster case routing

Expected impact:
- Reduced handling time
- Improved assignment speed
- Better prioritization of urgent cases

### 4. Risks
Risk level: Low

Why low:
- No schema migrations
- No backend API modifications
- Progressive enhancement on top of existing flows

Edge cases to monitor:
- Large datasets (DOM filtering performance)
- Priority value mismatch (handled via uppercase normalization)

### 5. Rollback Plan
Revert:
- `static/js/admin-requests-filters.js`
- `static/js/admin-requests-rowclick.js`
- `static/js/admin-requests-actionable-mark.js`
- `static/js/admin-copy-link.js`
- CSS additions in `static/css/pages/admin-ui.css`
- `data-*` attributes in `templates/admin/requests.html`

Result after rollback:
- System falls back to basic table view with existing backend behavior

---

### Milestone Positioning
This is not a UI refresh.

This is an **Operational Maturity Milestone**.

### Versioning Decision
Adopt product-stage versioning for major admin milestones:
- `Admin v3.0 - Operational Layer` (current)
- `Admin v3.1 - Reliability & Telemetry` (next stabilization/observability phase)
- `Admin v3.2 - Assisted Triage` (future intelligence layer)

This naming improves communication with associations, investors, and B2B partners.
