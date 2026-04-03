# Request Permission Model — Governance Baseline

## 1. Scope

This document defines the canonical permission model for the **Request domain** in HelpChain.

It applies to:

- admin panel actions (/admin/*)
- ops workflows (/ops/*)
- API mutation endpoints
- request-level object access and editability
- tenant-scoped access (multi-tenant behavior)

This document governs:

- who can read
- who can mutate
- who can perform high-risk operations
- how scope (global vs structure) is enforced

---

## 2. Canonical Admin Roles

The effective admin role set is:

- `superadmin`
- `ops`
- `readonly`

### Role Semantics

#### superadmin

- full system access
- can perform all mutations
- can perform global actions
- can operate across all structures

#### ops

- operational role
- can manage requests and cases within allowed scope
- cannot perform destructive or governance-level actions

#### readonly

- read-only access
- no mutation privileges

---

## 3. Role Normalization

### Current Runtime Reality

Legacy role values (e.g. `admin`) may still exist.

Normalization maps:

- `admin` → `superadmin`

### Rules

- Permission checks MUST use normalized role values
- New code MUST NOT rely on legacy role names
- Role evaluation MUST be consistent across all guard layers

---

## 4. Permission Surfaces

### Canonical Guard Stack

Source: admin routes

- `@admin_required`
- `admin_role_required(...)`
- `@operator_required`
- session-based admin validation
- MFA / fresh-auth for sensitive actions

### Rules

- All admin routes MUST use the canonical guard stack
- New routes MUST NOT introduce alternative permission systems
- Guard logic MUST be explicit and readable at route level

---

## 5. Request-Level Permissions

### Core Rule

Permissions MUST be enforced at both:

- route level (decorators)
- object level (request-specific checks)

---

## 6. Action Matrix

### Read Access

| Role       | Access                                  |
|------------|------------------------------------------|
| superadmin | all requests                             |
| ops        | requests within scope                    |
| readonly   | read-only access where explicitly allowed|

---

### Mutations (Operational)

| Action                     | superadmin | ops | readonly |
|--------------------------|------------|-----|----------|
| update status            | YES        | YES | NO       |
| assign/unassign owner    | YES        | YES | NO       |
| assign volunteer/pro     | YES        | YES | NO       |
| add note                 | YES        | YES | NO       |
| approve/reject interest  | YES        | YES | NO       |

---

### High-Privilege Actions

| Action             | superadmin | ops | readonly |
|--------------------|------------|-----|----------|
| archive            | YES        | NO  | NO       |
| delete             | YES        | NO  | NO       |
| restore            | YES        | NO  | NO       |
| unlock             | YES        | NO  | NO       |

---

### Governance Actions

| Action                     | superadmin | ops | readonly |
|--------------------------|------------|-----|----------|
| structure creation        | YES        | NO  | NO       |
| assign admin to structure | YES        | NO  | NO       |

---

## 7. Object-Level Edit Policy

### Source

`can_edit_request(...)`

### Rules

- superadmin → full edit access
- ops → allowed based on workflow and scope
- non-admin users → restricted to ownership logic

### Critical Rule

Object-level checks MUST NOT override role-based restrictions.

---

## 8. Scope Model (Multi-Tenant)

### Concepts

- Global admin → `structure_id IS NULL`
- Structure admin → `structure_id IS SET`

### Rules

- Non-global users MUST be scoped to their structure
- Queries MUST enforce structure filtering
- Direct object access MUST validate structure ownership

---

## 9. Scope Enforcement

### Rules

- Any Request fetch MUST validate scope unless explicitly global
- Any mutation MUST verify that the actor has access to that Request
- Direct DB access patterns (e.g. `db.session.get`) MUST NOT bypass scope validation

### Forbidden Drift

- fetching Request without scope check
- mutating Request outside of actor scope
- assuming global access without explicit validation

---

## 10. Mixed Guard Risk

### Current Runtime Reality

Some mutation paths use:

- `@login_required` + `can_edit_request`

instead of:

- role-based decorators

### Risk

- inconsistent enforcement
- privilege escalation potential
- unclear policy ownership

### Rules

- All Request mutations MUST use role-based guards
- `login_required` alone is insufficient for admin mutation
- object-level checks MUST complement, not replace, role checks

---

## 11. API Authorization

### Current Runtime Reality

API endpoints use mixed patterns:

- JWT-based role checks
- admin decorators
- weak or missing guards

### Rules

- API endpoints MUST enforce equivalent permission logic as admin routes
- API MUST NOT bypass role-based checks
- API MUST enforce canonical role semantics (superadmin / ops / readonly)

---

## 12. Denied Action Handling

### Rules

- All denied actions MUST be audited
- Denials MUST include:
  - actor_id
  - role
  - attempted action
  - reason (permission, scope)

---

## 13. Sensitive Action Protection

### Rules

Sensitive actions MUST require:

- MFA validation (if enabled)
- fresh authentication (session freshness)

Applies to:

- delete
- archive
- restore
- structure-level changes

---

## 14. Forbidden Future Drift

The following are explicitly forbidden:

- introducing new role names without governance update
- bypassing role decorators for convenience
- mixing role logic with ad hoc permission checks
- allowing ops to perform destructive actions
- relying on implicit access instead of explicit validation
- duplicating permission logic across modules

---

## 15. Immediate Risk Classes

### 1. Guard inconsistency risk

Mixed use of:

- role decorators
- login_required
- object checks

### 2. Scope bypass risk

Direct Request access without scope enforcement

### 3. API permission drift

Inconsistent authorization models across endpoints

### 4. Role normalization ambiguity

Legacy roles may still behave inconsistently

---

## 16. Enforcement

### Mandatory Rules

- Any Request mutation without role-based guard = blocking issue
- Any scope bypass = blocking issue
- Any API endpoint without proper authorization = blocking issue
- Any role inconsistency = must be flagged

### Review Checklist

For every mutation:

- Is role guard present?
- Is role correct (superadmin vs ops)?
- Is scope validated?
- Is object-level check aligned?
- Is denied action audited?

---

## 17. Summary

### Core Principle

Permissions define system safety.

### System Guarantee

- no unauthorized mutation
- no scope leakage
- no silent privilege escalation

### Governance Goal

The system MUST always answer:

👉 who can do what, where, and why — deterministically.
