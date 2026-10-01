# HelpChain — User Runtime Usage Audit

## Classification buckets

### A. OK domain-only
Usages where `User` is a domain/entity reference and not an auth family.

### B. Compatibility-only
Usages that exist for backward compatibility and should not be expanded.

### C. Should migrate
Usages that should move toward `AdminUser`, `Volunteer`, or another explicit model.

### D. Suspicious
Usages that may create auth ambiguity, identity confusion, or future regressions.

---

## Findings

_To be filled from code audit._

---

## Rules

- `User` must not become a new canonical login family
- New auth flows must not use `User`
- Domain references are allowed only when clearly documented
- Ambiguous runtime uses must be narrowed or migrated

## Findings

### A. OK domain-only

- `case_participant.user_id -> users.id`
- `PushSubscription.user_id -> users.id`

These are domain/entity references and are not canonical auth flows.

### B. Compatibility-only

- `main.py` test-only requester bootstrap under `TESTING`

This is acceptable as a testing compatibility path and must not be expanded into production auth logic.

### C. Should migrate / narrow

- `admin_cases.py` uses `User` as a selectable participant entity
- `admin_requests.py` creates or reuses a `User` record for internal requester workflows

These usages may remain temporarily but must be documented as domain/service actor usages, not authentication families.

### D. Suspicious

- `social_requests.py` resolves runtime actor identity from session keys into `User`
- `social_requests.py` uses `User` as assignee / actor in operational request flows

These usages may create identity ambiguity and should be narrowed or explicitly documented.