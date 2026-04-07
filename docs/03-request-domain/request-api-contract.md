# Request API Contract - Governance Baseline

## 1. Scope

This document defines the canonical API contract for the Request domain in HelpChain.

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

## 2. Core Principle

The API must not weaken system governance.

This means:

- the API must respect the status model
- the API must respect the permission model
- the API must respect the audit model
- the API must produce deterministic outcomes

## 3. Canonical Status Handling

### Rules

- The API must normalize all incoming status values using `normalize_request_status`.
- The API must reject invalid or unknown status values after normalization.
- The API must not write raw or unnormalized status values to `Request.status`.

### Required Behavior

```python
normalized = normalize_request_status(input_status)

if normalized not in REQUEST_STATUS_ALLOWED:
    abort(400)

request.status = normalized
```

### Forbidden

- direct assignment of `request.status = input_status`
- accepting `pending`, `approved`, or `rejected` as final stored values
- introducing new status literals through API behavior

## 4. Input Validation

### Rules

- All API inputs must be validated before processing.
- Required fields must be enforced.
- Types must be validated.
- Unknown fields should be rejected explicitly or ignored explicitly.

### Required Checks

- request existence
- actor authorization
- structure scope
- status validity
- transition validity where applicable

### Forbidden

- implicit coercion of invalid input
- silent fallback behavior
- accepting malformed payloads

## 5. Permission Enforcement

### Rules

- The API must enforce the same role model as admin routes.
- The API must not bypass role-based guards.

### Required

- role check (`superadmin`, `ops`, `readonly`)
- scope check (`structure_id`)
- object-level validation where applicable

### Forbidden

- trusting client-provided role
- skipping role validation for internal endpoints
- mixing authorization models across endpoints

## 6. Scope Enforcement

### Rules

- The API must enforce tenant scope for all Request access.
- Non-global users must only access Requests within their structure.
- Global actions must be explicitly validated.

### Required

- `structure_id` validation
- scoped query enforcement

### Forbidden

- direct `db.session.get(Request, id)` without scope validation
- cross-tenant access without explicit authorization

## 7. Audit Requirements

### Rules

- Every API mutation must generate an audit event.
- API-triggered audit must be equivalent to admin-triggered audit.

### Required

- call to `audit_admin_action`
- correct `action_type`
- metadata including previous and new values

### Forbidden

- silent mutations
- API writes without audit
- inconsistent audit between admin and API paths

## 8. Response Contract

### Success Response

API responses must be structured and predictable.

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

All errors must follow a consistent format:

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

- The API must fail explicitly and early.
- The API must return meaningful error codes.
- The API must not silently ignore errors.

### Required

- `400` for validation errors
- `403` for permission errors
- `404` for resource not found
- `500` for unexpected internal errors

### Forbidden

- returning success on partial failure
- masking permission errors as not found
- inconsistent error formats

## 10. Idempotency

### Rules

- The API should be idempotent where applicable.
- Repeated calls with the same input must not produce inconsistent state.

### Example

Setting status to the same value twice must not create duplicate side effects.

## 11. Transition Safety

### Rules

- The API must enforce valid status transitions.
- The API must not allow invalid lifecycle jumps.

### Example

Forbidden:

- `done -> in_progress`
- `cancelled -> open`

Allowed:

- `open -> in_progress`
- `in_progress -> done`
- `in_progress -> cancelled`

## 12. Bulk Operations

### Rules

- Bulk operations must apply validation per item.
- Bulk operations must produce per-request audit entries.
- Partial failure must be explicitly reported.

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

- The API must operate on the latest consistent data.
- The API must not produce conflicting states.
- Write operations must be atomic per request.

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

### 1. Raw Write Risk

Direct assignment of status without normalization.

### 2. Permission Drift

API endpoints not aligned with the admin role model.

### 3. Audit Gaps

API mutations without audit logging.

### 4. Response Inconsistency

Different formats across endpoints.

### 5. Scope Leakage

Cross-tenant access due to missing validation.

## 16. Enforcement

### Mandatory Rules

- any API mutation without normalization is a blocking issue
- any API mutation without audit is a blocking issue
- any API endpoint without permission enforcement is a blocking issue
- any inconsistent response format must be fixed

### Review Checklist

For every API endpoint:

- input validated
- status normalized
- permissions enforced
- scope enforced
- audit triggered
- response structured
- errors consistent

## 17. Summary

### Core Principle

The API is a controlled interface, not a shortcut.

### System Guarantee

- no invalid writes
- no unauthorized access
- no silent mutations
- no inconsistent behavior

### Governance Goal

The API must behave exactly like the admin system: not weaker, not different, not optional.
