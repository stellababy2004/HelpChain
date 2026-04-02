# Request API Contract — Governance Baseline

## 1. Scope

This document defines the canonical API contract for the **Request domain** in HelpChain.

It applies to:

- all `/api/*` endpoints interacting with Request
- admin-triggered API endpoints
- ops API endpoints
- external or internal integrations
- any programmatic access layer modifying Request

It governs:

- input validation
- status handling
- permission enforcement
- audit requirements
- response structure
- error handling
- consistency guarantees

---

## 2. Core Principle

The API MUST NOT break system governance.

This means:

- API MUST respect status model
- API MUST respect permission model
- API MUST respect audit model
- API MUST produce deterministic outcomes

---

## 3. Canonical Status Handling

### Rules

- API MUST normalize all incoming status values using `normalize_request_status`
- API MUST reject invalid or unknown status values after normalization
- API MUST NOT write raw or unnormalized status values to `Request.status`

### Required Behavior

```python
normalized = normalize_request_status(input_status)

if normalized not in REQUEST_STATUS_ALLOWED:
    abort(400)

request.status = normalized
```

### Forbidden

- direct assignment of request.status = input_status
- accepting pending, approved, rejected as final stored values
- introducing new status literals via API

## 4. Input Validation

### Rules

- All API inputs MUST be validated before processing
- Required fields MUST be enforced
- Types MUST be validated (string, int, enum, etc.)
- Unknown fields SHOULD be rejected or ignored explicitly

### Required Checks

- request existence
- actor authorization
- structure scope
- status validity
- transition validity (if applicable)

### Forbidden

- implicit coercion of invalid input
- silent fallback behavior
- accepting malformed payloads

## 5. Permission Enforcement

### Rules

- API MUST enforce the same role model as admin routes
- API MUST NOT bypass role-based guards

### Required

- role check (superadmin / ops / readonly)
- scope check (structure_id)
- object-level validation (request ownership where applicable)

### Forbidden

- trusting client-provided role
- skipping role validation for internal endpoints
- mixing authorization models across endpoints

## 6. Scope Enforcement

### Rules

- API MUST enforce tenant scope for all Request access
- non-global users MUST only access Requests within their structure
- global actions MUST be explicitly validated

### Required

- structure_id validation
- scoped query enforcement

### Forbidden

- direct db.session.get(Request, id) without scope validation
- cross-tenant access without explicit authorization

## 7. Audit Requirements

### Rules

- Every API mutation MUST generate an audit event
- API-triggered audit MUST be equivalent to admin-triggered audit

### Required

- call to audit_admin_action
- correct action_type
- metadata including previous and new values

### Forbidden

- silent mutations
- API write without audit
- inconsistent audit between admin and API paths

## 8. Response Contract

### Success Response

API responses MUST be structured and predictable.

Example:

```json
{
  "status": "success",
  "data": {
    "request_id": 123,
    "status": "in_progress"
  }
}
```

### Error Response

All errors MUST follow a consistent format:

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_STATUS",
    "message": "Invalid request status"
  }
}
```

## 9. Error Handling

### Rules

- API MUST fail explicitly and early
- API MUST return meaningful error codes
- API MUST NOT silently ignore errors

### Required

- 400 -> validation errors
- 403 -> permission errors
- 404 -> resource not found
- 500 -> internal error (unexpected)

### Forbidden

- returning success on partial failure
- masking permission errors as not found
- inconsistent error formats

## 10. Idempotency

### Rules

- API SHOULD be idempotent where applicable
- repeated calls with same input MUST not produce inconsistent state

### Example

setting status to same value twice MUST not create duplicate side effects

## 11. Transition Safety

### Rules

- API MUST enforce valid status transitions
- API MUST NOT allow invalid lifecycle jumps

### Example

Forbidden:

- done -> in_progress
- cancelled -> open

Allowed:

- open -> in_progress
- in_progress -> done
- in_progress -> cancelled

## 12. Bulk Operations

### Rules

- bulk operations MUST apply validation per item
- bulk operations MUST produce per-request audit entries
- partial failure MUST be explicitly reported

### Required Response

```json
{
  "status": "partial_success",
  "results": [
    {"request_id": 1, "status": "ok"},
    {"request_id": 2, "status": "error", "error": "INVALID_STATUS"}
  ]
}
```

## 13. Data Consistency

### Rules

- API MUST operate on latest consistent data
- API MUST NOT produce conflicting states
- write operations MUST be atomic per request

## 14. Forbidden Future Drift

The following are explicitly forbidden:

- bypassing normalization
- bypassing permission checks
- bypassing audit
- introducing new status vocabularies
- inconsistent response formats
- mixing admin and API behavior
- silent failure paths

## 15. Immediate Risk Classes

### 1. Raw write risk

Direct assignment of status without normalization

### 2. Permission drift

API endpoints not aligned with admin role model

### 3. Audit gaps

API mutations without audit logging

### 4. Response inconsistency

Different formats across endpoints

### 5. Scope leakage

Cross-tenant access due to missing validation

## 16. Enforcement

### Mandatory Rules

- any API mutation without normalization = blocking issue
- any API mutation without audit = blocking issue
- any API endpoint without permission enforcement = blocking issue
- any inconsistent response format = must be fixed

### Review Checklist

For every API endpoint:

- input validated?
- status normalized?
- permissions enforced?
- scope enforced?
- audit triggered?
- response structured?
- errors consistent?

## 17. Summary

### Core Principle

API is a controlled interface, not a shortcut.

### System Guarantee

- no invalid writes
- no unauthorized access
- no silent mutations
- no inconsistent behavior

### Governance Goal

The API MUST behave exactly like the admin system -
not weaker, not different, not optional.

---

# 🧠 Къде си вече (реално)

Ти току-що си изгради:

| Layer        | Статус |
|-------------|--------|
| Status      | 🔒 HARD LOCK |
| Audit       | 🔒 HARD LOCK |
| Permissions | 🔒 HARD LOCK |
| API         | 🔒 HARD LOCK |


