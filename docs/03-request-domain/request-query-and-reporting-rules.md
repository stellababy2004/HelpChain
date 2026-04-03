# Request Query and Reporting Rules — Governance Baseline

## 1. Scope

This document defines the canonical rules for querying, aggregating, and reporting on the **Request** domain.

It applies to:

- admin dashboards (/admin/*)
- ops dashboards (/ops/*)
- KPI endpoints (/admin/api/*, /api/*)
- volunteer/requester views
- analytics and reporting layers
- any SQL/ORM query touching Request status or lifecycle

It governs:

- query correctness
- status interpretation
- KPI aggregation
- visibility logic
- consistency guarantees

---

## 2. Core Principle

All queries MUST reflect **canonical system truth**.

This means:

- no reliance on raw legacy status values
- no mixed vocabularies
- no divergence between views (admin vs volunteer vs API)

---

## 3. Canonical Status Interpretation

### Rules

- All queries MUST interpret Request status using normalized canonical values.
- Raw stored values MUST NOT be used directly for business logic without normalization.
- Equivalent states (e.g. `pending` and `open`) MUST NOT be split into separate query buckets.

### Canonical mapping

All Request states MUST resolve to:

- `open`
- `in_progress`
- `done`
- `cancelled`

---

## 4. Query Normalization Requirement

### Rules

- Any query filtering by status MUST account for legacy aliases OR operate on normalized values.
- Any query grouping by status MUST group by canonical normalized value.

### Example (transitional safe)

```python
or_(
    Request.status == "open",
    Request.status == "pending"
)
```
