# Request Status Model — Governance Baseline

## 1. Scope

This document defines the canonical status model for the **Request** domain in HelpChain.

It applies to:

- request creation
- request updates
- request assignment workflows
- volunteer/requester visibility logic
- admin workflows
- KPI / dashboard logic
- API write and read paths
- audit / lifecycle side effects

This document does **not** define the legacy `SocialRequest` lifecycle except where comparison is necessary to identify conflict or forbidden drift.

---

## 2. Canonical Request Status Set

The canonical Request status set MUST be limited to:

- `open`
- `in_progress`
- `done`
- `cancelled`

These four values are the only canonical business statuses for the `Request` model.

### Rules

- New Request-domain logic MUST use only the canonical status set.
- New Request-domain features MUST NOT introduce additional primary status values.
- Operational, UI, API, and reporting logic MUST interpret Request lifecycle state through this canonical set.

---

## 3. Legacy Aliases and Normalization

The following legacy alias mappings are currently recognized for compatibility:

- `pending` → `open`
- `approved` → `in_progress`
- `rejected` → `cancelled`

### Rules

- Runtime logic MUST normalize legacy aliases before making workflow, permission, KPI, or visibility decisions.
- Legacy aliases MUST be treated as compatibility inputs, not canonical business states.
- New code MUST NOT rely on raw alias values as if they were canonical statuses.
- New code MUST NOT introduce additional aliases without explicit governance update.

### Current Runtime Reality

The current codebase still contains stored legacy values in active Request rows and active code paths. This is compatibility debt, not canonical direction.

---

## 4. Stored Values vs Effective Values

### Current Runtime Reality

The `Request.status` field is currently stored as a free string and legacy values may still exist in storage.

This means:

- stored value may be `pending`
- effective business meaning may be `open`

### Rules

- Any read path that makes workflow or business decisions MUST use normalized status semantics.
- Any write path SHOULD persist canonical values directly whenever feasible.
- Raw stored values MUST NOT be treated as authoritative business semantics without normalization.
- Reviewers MUST treat any business logic based directly on unnormalized legacy values as a risk.

### Canonical Direction

The target system state is:

- stored value = canonical value
- effective value = canonical value

That means the long-term direction is to remove dependency on stored legacy aliases in active Request behavior.

---

## 5. Request Creation Rules

### Current Runtime Reality

Some active creation flows still write:

- `status = "pending"`

This is runtime-compatible only because alias normalization later treats `pending` as `open`.

### Governance Rules

- New Request creation paths SHOULD write `open` directly.
- New Request creation paths MUST NOT introduce new legacy write values.
- Existing creation paths that still write `pending` MUST be treated as transitional compatibility debt.
- Any new intake flow MUST align with canonical Request status semantics at write time.

### Forbidden Drift

- New request creation code MUST NOT write `approved`, `rejected`, `resolved`, `completed`, `active`, or `closed` into `Request.status`.
- New request creation code MUST NOT expand compatibility debt.

---

## 6. Request Transition Rules

The canonical Request lifecycle is:

- `open` → `in_progress`
- `in_progress` → `done`
- `in_progress` → `cancelled`
- `open` → `cancelled`

### Transition Semantics

- `open` means created and actionable
- `in_progress` means active operational handling has started
- `done` means successfully completed
- `cancelled` means terminated or closed without successful completion

### Rules

- Admin and operational flows MUST enforce transitions against canonical normalized values.
- Terminal states are:
  - `done`
  - `cancelled`
- Terminal states MUST lock or restrict actions according to workflow policy.
- Completion-related side effects MUST be triggered from canonical terminal semantics, not legacy aliases.

### Forbidden Drift

- New modules MUST NOT define alternate terminal-state logic independently.
- New code MUST NOT treat `rejected`, `resolved`, `completed`, or `closed` as separate canonical Request states.

---

## 7. Read / Query Rules

### Rules

- Query logic that determines visibility, actionability, state grouping, or permissions MUST evaluate effective normalized status.
- UI filters MUST NOT silently exclude Requests that are canonically equivalent but still stored with legacy aliases.
- Volunteer-facing and requester-facing visibility logic MUST remain semantically aligned with admin logic.

### Example Risk

A query that filters only:

- `status = "open"`

while active rows may still be stored as:

- `status = "pending"`

creates visibility drift and is therefore non-compliant with this baseline.

### Governance Rule

Any read/query path that uses raw status literals for Request business behavior MUST be reviewed for normalization safety.

---

## 8. API Rules

### Rules

- All API write paths that mutate `Request.status` MUST normalize inputs before persistence.
- API write paths MUST reject unknown or non-canonical status values after normalization.
- API read/reporting paths MUST use canonical normalized semantics when grouping or counting Request states.
- API endpoints MUST NOT bypass canonical status validation.

### Forbidden Drift

The following are explicitly forbidden in new code:

- direct raw assignment of arbitrary status strings into `Request.status`
- accepting legacy or custom status strings without normalization and validation
- reporting Request status buckets using mixed raw vocabularies without canonical mapping

---

## 9. KPI / Dashboard / Operational Reporting Rules

### Current Runtime Reality

Some KPI, dashboard, and ops surfaces still aggregate raw stored status values and therefore may split canonically equivalent states into different buckets.

Examples of risk:

- `pending` counted separately from `open`
- `rejected` counted separately from `cancelled`
- `resolved` / `completed` / `active` used as operational vocabulary near canonical Request reporting

### Rules

- KPI and dashboard logic MUST aggregate Request lifecycle state through canonical normalized status semantics.
- Reporting layers MUST NOT treat alias values as separate business buckets.
- Operational dashboards MUST NOT invent alternate Request lifecycle vocabularies outside the canonical set.

### Canonical Reporting Buckets

Reporting for Request MUST resolve into these buckets only:

- `open`
- `in_progress`
- `done`
- `cancelled`

Any secondary labels must be explicitly derived presentation labels, not alternate stored state systems.

---

## 10. Permission and Workflow Coupling

### Rules

- Any permission logic, lock logic, or editability rule based on Request status MUST use normalized canonical status.
- Terminal-state restrictions MUST evaluate canonical terminal states only.
- Workflow side effects such as completion timestamps, activity logs, audit events, and action locks MUST remain aligned with canonical lifecycle state.

### Forbidden Drift

- Modules MUST NOT maintain separate hidden closure definitions for Request.
- New code MUST NOT use inconsistent “closed sets” such as ad hoc mixtures of `done`, `rejected`, `completed`, or `closed`.

---

## 11. Comparison with Legacy Systems

### SocialRequest

`SocialRequest` uses a separate lifecycle vocabulary and is not authoritative for the canonical `Request` status model.

### Rules

- SocialRequest vocabulary MUST NOT influence new Request-domain status logic.
- Legacy comparisons MAY be documented for migration or compatibility analysis only.
- New Request-domain features MUST NOT borrow lifecycle semantics from SocialRequest.

---

## 12. Immediate Risk Classes

The following are recognized active risk classes:

1. **Stored-vs-effective divergence risk**  
   Legacy stored values remain present while normalized logic assumes canonical semantics.

2. **API bypass risk**  
   Any endpoint that writes raw Request status without normalization can corrupt lifecycle governance.

3. **Metrics drift risk**  
   Raw status aggregation can produce inconsistent KPI and ops reporting.

4. **Visibility drift risk**  
   User-facing queries may exclude canonically valid Requests if they rely on raw legacy values.

5. **Parallel vocabulary pressure**  
   Legacy request systems and old operational terms can reintroduce non-canonical lifecycle semantics.

---

## 13. Enforcement

### Mandatory Enforcement Rules

- Any code path that writes `Request.status` MUST be reviewed for canonical normalization compliance.
- Any code path that reads `Request.status` for business decisions MUST be reviewed for normalization compliance.
- Any violation of the canonical status set MUST be treated as a blocking review issue.
- Any ambiguity between runtime compatibility behavior and canonical direction MUST be documented before modification.

### Review Rule

When runtime behavior and canonical direction differ:

- runtime reality MUST be documented
- canonical direction MUST remain the governing target
- convenience MUST NOT override canonical lifecycle rules

---

## 14. Summary

### Canonical Truth

The HelpChain `Request` lifecycle is governed by exactly four canonical statuses:

- `open`
- `in_progress`
- `done`
- `cancelled`

### Compatibility Truth

Legacy aliases still exist and must currently be normalized for safe operation.

### Governance Truth

All future work MUST reduce, not expand, dependence on:

- raw legacy writes
- mixed vocabularies
- unnormalized reads
- status-based reporting drift
