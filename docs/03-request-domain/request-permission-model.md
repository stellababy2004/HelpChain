# Request Permission Model — Governance Baseline

## 1. Scope

This document defines the canonical permission model for the **Request domain** in HelpChain.

**Authority: CURRENT / SOURCE OF TRUTH — GOVERNANCE CONTRACT**

This document defines the permission rules that Request-domain work must follow. It does not claim that every current route already implements the contract uniformly. Application code, route guards, actor policies, and focused tests remain authoritative for current implementation.

The contract applies to the `Request` portion of the canonical `Request → Case → Assignment` spine. It does not automatically grant equivalent access to Case or Assignment surfaces; those require their own scoped authorization.

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

The canonical administrative role set is:

- `superadmin`
- `admin`
- `ops`
- `readonly`

### Role Semantics

#### platform-global superadmin

- authenticated active `AdminUser`;
- canonical role `superadmin`;
- no attached `structure_id`;
- may perform cross-structure operations only where the relevant route or policy permits.

#### structure-attached superadmin

- canonical role `superadmin`;
- attached `structure_id`;
- remains restricted to that structure;
- is not platform-global.

#### admin

- structure-level administrative role;
- manages permitted Request operations within the attached structure;
- does not receive platform-global access through role normalization.

#### ops

- operational role;
- can perform explicitly permitted workflow actions within its attached structure;
- cannot infer destructive or governance access from the role name alone.

#### readonly

- read-only access where explicitly implemented;
- remains tenant-scoped;
- has no mutation authority under this governance contract.

---

## 3. Role Normalization

### Current Implementation

Current canonical normalization maps:

- `admin` → `admin`;
- `superadmin` → `superadmin`;
- `super_admin` → `superadmin`;
- `super-admin` → `superadmin`;
- `ops` → `ops`;
- `readonly` and `read-only` → `readonly`.

### Governance Rules

- Permission checks MUST use canonical role values.
- `admin` MUST NOT be normalized or promoted to `superadmin`.
- Legacy superadmin aliases MUST NOT create a second permission model.
- Role evaluation MUST remain consistent across actor resolution, route guards, policies, and tests.

---

## 4. Permission Surfaces

### Canonical Guard Stack

Source: admin routes

- `@admin_required`
- `admin_role_required(...)`
- `@operator_required`
- session-based admin validation
- MFA / fresh-auth for sensitive actions

### Governance Rules

- Request access MUST combine the applicable authentication, role, tenant, and object-level checks.
- New routes MUST NOT introduce an alternative permission system.
- Guard logic MUST be explicit and readable at route or policy level.
- A role check alone MUST NOT be treated as proof of tenant access.
- Existing routes use mixed guard patterns and must be verified individually before their behavior is described as implemented.

---

## 5. Request-Level Permissions

### Core Rule

Permissions MUST be enforced at both:

- route level (decorators)
- object level (request-specific checks)

---

## 6. Action Matrix

The following tables are the **governance contract**, not a complete inventory of current route enforcement. “Within scope” means the actor also passes the relevant tenant, object, route, and MFA/fresh-auth checks.

### Read Access

| Actor | Access |
| --- | --- |
| platform-global superadmin | cross-structure Request access where the route policy permits |
| structure-attached superadmin | Requests within the attached structure |
| admin | Requests within the attached structure |
| ops | Requests within permitted operational scope |
| readonly | read-only access where explicitly allowed and within tenant scope |

---

### Mutations (Operational)

| Action | superadmin | admin | ops | readonly |
| --- | --- | --- | --- | --- |
| update status | within scope | within scope | within permitted workflow | NO |
| assign/unassign owner | within scope | within scope | within permitted workflow | NO |
| assign volunteer/pro | within scope | within scope | within permitted workflow | NO |
| add note | within scope | within scope | within permitted workflow | NO |
| approve/reject interest | within scope | within scope | within permitted workflow | NO |

---

### High-Privilege Actions

| Action | platform-global superadmin | structure-bound administrative actor | ops | readonly |
| --- | --- | --- | --- | --- |
| archive | only where explicitly permitted | route-policy specific and tenant-scoped | NO | NO |
| delete | only where explicitly permitted | route-policy specific and tenant-scoped | NO | NO |
| restore | only where explicitly permitted | route-policy specific and tenant-scoped | NO | NO |
| unlock | only where explicitly permitted | route-policy specific and tenant-scoped | NO | NO |

---

### Governance Actions

| Action | platform-global superadmin | structure-attached superadmin | admin | ops | readonly |
| --- | --- | --- | --- | --- | --- |
| structure creation | where explicitly permitted | NO | NO | NO | NO |
| cross-structure administration | where explicitly permitted | NO | NO | NO | NO |

---

## 7. Object-Level Edit Policy

### Source

Current routes use a combination of guards, scoped queries, policies, and helpers such as `can_edit_request(...)`.

### Current Implementation Caveat

`can_edit_request(...)` currently:

- returns `True` immediately for `admin`, `superadmin`, and the legacy `super_admin` alias;
- otherwise falls back to owner matching;
- does not itself enforce tenant scope.

It is therefore not a complete authorization decision and MUST NOT be used without the applicable route guard and tenant-scoped object lookup.

### Governance Rule

Object-level helpers MUST complement, not override or replace, authentication, role, tenant, and route-policy restrictions.

---

## 8. Scope Model (Multi-Tenant)

### Concepts

- Platform-global actor → authenticated canonical `superadmin` with `structure_id IS NULL`
- Structure-attached superadmin → canonical `superadmin` with `structure_id IS SET`
- Structure admin → canonical `admin` with `structure_id IS SET`
- Structure ops → canonical `ops` with `structure_id IS SET`

### Rules

- Platform-global access MUST require the full invariant, not only a role label.
- A structure-attached superadmin MUST remain tenant-scoped.
- Admin and ops actors MUST remain scoped to their structure.
- Queries MUST enforce structure filtering.
- Direct object access MUST validate structure ownership.
- A platform-global actor may bypass tenant filtering only where the relevant policy permits it.

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

- API endpoints MUST enforce equivalent authentication, role, tenant, and object-level rules for the operation they expose.
- API authorization MUST NOT bypass tenant checks merely because a valid JWT is present.
- API role handling MUST preserve the distinct canonical roles `superadmin`, `admin`, `ops`, and `readonly`.

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

- Is the applicable authentication and role guard present?
- Is the role correct (`superadmin`, `admin`, `ops`, or `readonly`)?
- If superadmin is treated as global, is `structure_id` absent and is the route policy explicitly global?
- Is scope validated?
- Is object-level check aligned?
- Is denied action audited?

---

## 17. Summary

### Core Principle

Permissions define system safety.

### Required Security Objectives

- no unauthorized mutation
- no scope leakage
- no silent privilege escalation

### Governance Goal

The permission model and its implementation MUST make it possible to answer:

👉 who can do what, where, and why — deterministically.
