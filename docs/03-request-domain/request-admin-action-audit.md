# Request Admin Action Audit — Governance Baseline

## 1. Scope

This document defines the audit and traceability model for all **admin and operational actions** performed on the Request domain.

It applies to:

- admin panel actions (/admin/*)
- ops actions (/ops/*)
- API-triggered admin mutations
- automated system-triggered state changes (where applicable)

It covers:

- audit event creation
- audit event consistency
- audit coverage requirements
- audit integrity and reliability
- linkage with Request timeline/history

---

## 2. Core Audit Principle

All state-changing or risk-relevant actions on Request MUST be auditable.

### Definition

An action is considered auditable if it:

- changes Request.status
- changes ownership (assign/unassign)
- changes priority or classification
- adds or modifies operational notes
- performs destructive operations (delete, archive, restore)
- affects workflow progression
- represents a denied or blocked action

---

## 3. Audit Sources

### Canonical Audit Table

Source: `backend/models.py::AdminAuditEvent`

This is the canonical persisted audit ledger.

### Supporting Timeline Tables

- `RequestActivity`
- `CaseEvent` (for case-linked actions)

These provide **operational timeline context**, but do NOT replace AdminAuditEvent.

---

## 4. Required Audit Events

The following actions MUST generate a persisted AdminAuditEvent:

### Request lifecycle

- status change (manual or automated)
- bulk status change (one event per request)
- archive / unarchive
- delete / restore

### Assignment

- assign owner
- unassign owner
- assign volunteer / professional
- unassign volunteer / professional

### Interaction

- note added
- manual intervention (e.g. nudge)

### Workflow triggers

- volunteer interest approve/reject
- request-to-case conversion

### Security / access

- denied action attempts
- unauthorized mutation attempts

---

## 5. Audit Event Structure

Each AdminAuditEvent MUST include:

- `actor_id` (who performed the action)
- `actor_role`
- `action_type` (normalized string)
- `target_type` (e.g. "request")
- `target_id`
- `timestamp`
- `metadata` (JSON payload)

### Metadata Requirements

Metadata MUST include:

- previous value (if applicable)
- new value (if applicable)
- contextual identifiers (structure_id, request_id)
- relevant flags (bulk_action, automated, etc.)

---

## 6. Action Naming (Canonical)

All audit events MUST use normalized action_type values.

### Examples

- `request.status_changed`
- `request.assigned`
- `request.unassigned`
- `request.note_added`
- `request.archived`
- `request.deleted`
- `request.restored`
- `request.interest_approved`
- `request.interest_rejected`
- `request.nudged`
- `request.case_created`
- `admin.denied_action`

### Rules

- New actions MUST follow `{domain}.{action}` naming
- New code MUST NOT invent inconsistent action naming patterns
- Action naming MUST be stable across admin, API, and background flows

---

## 7. Coverage Rules

### Mandatory Coverage

Every Request mutation MUST:

- trigger an audit event
- and (if applicable) append to RequestActivity timeline

### Forbidden Gaps

The following are forbidden:

- silent state changes
- mutations without audit trail
- partial audit (e.g. status changed but no metadata)
- bulk actions without per-request audit

---

## 8. Denied Action Auditing

### Rules

All denied admin actions MUST be logged via:

- `_audit_denied_action`

### Must include:

- attempted action
- actor_id
- actor_role
- reason (permission, scope, validation)

### Purpose

Denied-action audit is required for:

- security visibility
- anomaly detection
- compliance traceability

---

## 9. API Audit Rules

### Rules

- API endpoints that mutate Request MUST produce the same audit events as admin routes
- API-triggered audit MUST NOT be weaker than admin-triggered audit
- API MUST NOT bypass audit creation

### Forbidden

- direct DB mutation without audit
- silent API state change
- inconsistent action_type between admin and API paths

---

## 10. Timeline vs Audit Distinction

### RequestActivity (timeline)

- user-facing / operational history
- readable sequence of events

### AdminAuditEvent (audit)

- compliance-grade log
- immutable source of truth
- used for investigation and governance

### Rule

Audit MUST NOT be replaced by timeline events.

Both layers MUST coexist and remain consistent.

---

## 11. Integrity Rules

### Rules

- audit events MUST be append-only
- audit events MUST NOT be modified after creation
- audit timestamps MUST be consistent and server-generated
- audit MUST survive transaction rollback inconsistencies

---

## 12. Multi-Tenant / Scope Context

### Rules

- every audit event MUST include structure context (structure_id)
- global admin actions MUST still be traceable to a structure scope when relevant
- cross-tenant actions MUST be auditable and reviewable

---

## 13. Immediate Risk Classes

### 1. Missing audit coverage

Some Request mutations are currently not consistently audited (e.g. note add, delete, nudge, volunteer assignment).

### 2. Inconsistent audit pathways

Some code paths use:

- audit_admin_action
others:
- no audit
or
- timeline only

### 3. API audit gaps

Some API endpoints may mutate Request without consistent audit logging.

### 4. Bulk action audit gaps

Bulk operations may not produce per-request audit entries.

---

## 14. Enforcement

### Mandatory Rules

- Any Request mutation without audit MUST be treated as a blocking issue
- Any new endpoint that mutates Request MUST include audit coverage
- Any audit inconsistency MUST be flagged during review

### Review Checklist

For every Request mutation:

- Is audit_admin_action called?
- Does it include previous + new value?
- Is action_type canonical?
- Is metadata complete?
- Is structure_id present?

---

## 15. Summary

### Core Principle

Every meaningful action on Request MUST be traceable.

### System Goal

- full traceability
- consistent audit model
- no silent mutations
- no ambiguity in who did what and when

### Governance Goal

Audit is not a feature.  
Audit is a **system guarantee**.
