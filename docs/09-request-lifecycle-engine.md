# Request Lifecycle Engine — Governance Baseline

## 1. Scope

This document defines the canonical lifecycle engine for the **Request** domain in HelpChain.

It governs:

- Request state transitions
- transition validation
- state-derived locking/editability
- completion / terminal side effects
- audit and timeline coupling
- automation hooks triggered by lifecycle changes

It applies to:

- admin routes
- ops routes
- API mutation paths
- volunteer-driven operational transitions
- background/automation-triggered state changes

This document does **not** define the legacy `SocialRequest` lifecycle except where comparison is needed to identify conflict or forbidden drift.

---

## 2. Canonical State Machine

The canonical Request lifecycle MUST be limited to these states:

- `open`
- `in_progress`
- `done`
- `cancelled`

### Canonical transition graph

Allowed transitions:

- `open` → `in_progress`
- `open` → `cancelled`
- `in_progress` → `done`
- `in_progress` → `cancelled`

Optional no-op transitions:

- `open` → `open`
- `in_progress` → `in_progress`
- `done` → `done`
- `cancelled` → `cancelled`

### Terminal states

The following states are terminal:

- `done`
- `cancelled`

### Rules

- New Request-domain logic MUST enforce transitions against this canonical state machine.
- New code MUST NOT introduce alternate lifecycle graphs for `Request`.
- New code MUST NOT treat legacy alias values as separate states.

---

## 3. Normalization Before Decisioning

### Rules

- Any lifecycle decision MUST be based on normalized status.
- Any transition validation MUST occur on normalized status values.
- Any locking/editability logic MUST use normalized terminal semantics.

### Canonical rule

```python
old_status = normalize_request_status(request.status)
new_status = normalize_request_status(input_status)
```
