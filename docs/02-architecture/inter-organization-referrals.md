# Inter-Organization Referrals

## Purpose

This document defines a minimal foundation for inter-organization referrals in HelpChain.
It is a design pass only: no production schema change, route change, or UI implementation is
required yet.

The core principle is tenant isolation first, coordination second. A referral must be an
explicit, auditable exchange between two structures. It must not grant automatic access to
the source request, source case, internal notes, participants, assignments, or tenant lists.

## Current Model Findings

### Structures and tenant boundary

- `Structure` is the tenant boundary (`backend/models.py::Structure`), with `id`, `name`,
  `slug`, `status`, and `created_at`.
- `current_structure_id()` (`backend/core/tenant.py`) resolves the active structure from
  `current_user.structure_id`, `g.structure_id`, or a guarded default tenant fallback.
- Admin request queries use `_structure_scope_filter()` and `_scope_requests()` to filter
  `Request.structure_id` unless the actor is a global superadmin.

### Requests

- `Request` is the canonical operational work object.
- `Request.structure_id` links requests to a structure, currently nullable for legacy
  compatibility but treated by routes as the primary scope key.
- `Request.owner_id` links to `AdminUser`; request history is supported by `RequestLog`
  and `RequestActivity`.
- `HelpRequest` is an alias to `Request`.

### Cases

- `Case` is the newer case stack. It is one-to-one with `Request` through
  `Case.request_id`, has its own nullable `structure_id`, and carries operational state
  such as owner, professional lead, status, priority, risk, and activity timestamps.
- Case list scoping is built from scoped request IDs, then joined back to cases. This is
  a useful pattern because it keeps `Request.structure_id` as the canonical tenant guard.
- `CaseEvent` provides a case timeline with `visibility`, but it is operational history,
  not a compliance-grade replacement for admin audit.

### Admins and roles

- `AdminUser.structure_id` scopes structure admins/operators/readonly users.
- Current canonical admin roles include `readonly`, `ops`, `admin`, and `superadmin`.
- Mutation routes generally allow `ops`, `admin`, and `superadmin`; readonly can view but
  cannot mutate. The referral design should preserve that split.

### Participants and collaborators

- `CaseParticipant` models people or external contacts attached to a case. It is not an
  inter-tenant access grant.
- `CaseCollaborator` can associate another `Structure` to a case with a role. Today this is
  closer to a case sharing primitive than a safe referral primitive. It should not be used
  as the first referral foundation because it risks implying broader case access.
- Existing `POST /api/cases/<case_id>/invite-structure` creates `CaseCollaborator` and a
  `CaseEvent`. This endpoint is useful evidence of the need, but referrals should be more
  restrictive and auditable.

### Audit/activity patterns

- `AdminAuditEvent` is the canonical privileged-action ledger.
- `RequestActivity`, `RequestLog`, `CaseEvent`, and `SocialRequestEvent` are useful
  operational timelines, but they should not replace `AdminAuditEvent`.
- `SecurityEvent` supports structured security/audit events without PII and can be useful
  for denied referral actions or unusual cross-tenant probes.
- `SocialRequest` is a separate scoped flow with `structure_id` and its own events. Treat it
  as legacy/parallel, not the primary referral source for the first implementation.

## Referral Concept

Introduce a sealed referral record that references a source tenant, a target tenant, and one
originating object. The referral carries a deliberately limited shared snapshot. It does not
grant the target tenant access to the source request/case.

### Proposed model

```python
class OrganizationReferral(db.Model):
    __tablename__ = "organization_referrals"

    id = db.Column(db.Integer, primary_key=True)
    source_structure_id = db.Column(db.Integer, db.ForeignKey("structures.id"), nullable=False, index=True)
    target_structure_id = db.Column(db.Integer, db.ForeignKey("structures.id"), nullable=False, index=True)

    source_request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=True, index=True)
    source_case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=True, index=True)
    target_request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=True, index=True)
    target_case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=True, index=True)

    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    reason_category = db.Column(db.String(64), nullable=False, index=True)
    reason_note = db.Column(db.Text, nullable=True)
    consent_basis = db.Column(db.String(64), nullable=False)
    consent_note = db.Column(db.Text, nullable=True)
    shared_payload_json = db.Column(db.Text, nullable=False)
    privacy_level = db.Column(db.String(32), nullable=False, default="minimum")

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False, index=True)
    decided_by_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.CheckConstraint("source_structure_id <> target_structure_id", name="ck_referral_distinct_structures"),
        db.CheckConstraint(
            "(source_request_id IS NOT NULL) OR (source_case_id IS NOT NULL)",
            name="ck_referral_has_source_object",
        ),
        db.Index("ix_referrals_source_status_created", "source_structure_id", "status", "created_at"),
        db.Index("ix_referrals_target_status_created", "target_structure_id", "status", "created_at"),
        db.Index("ix_referrals_source_request_status", "source_request_id", "status"),
        db.Index("ix_referrals_source_case_status", "source_case_id", "status"),
    )
```

Use `shared_payload_json` as an explicit snapshot. It should contain only fields selected
for referral, for example:

- summary/title
- category and urgency
- non-sensitive location granularity
- contact handoff details only when consent allows it
- source organization display name
- consent/justification metadata

Do not place full request descriptions, internal case notes, private participant lists,
assignment history, risk signals, raw addresses, or free-form internal audit data in this
snapshot by default.

### Optional event model

If `AdminAuditEvent` payloads become too large or referral-specific history needs a public
timeline, add a narrow append-only table:

```python
class OrganizationReferralEvent(db.Model):
    __tablename__ = "organization_referral_events"

    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey("organization_referrals.id"), nullable=False, index=True)
    actor_admin_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True)
    actor_structure_id = db.Column(db.Integer, db.ForeignKey("structures.id"), nullable=True, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    old_status = db.Column(db.String(32), nullable=True)
    new_status = db.Column(db.String(32), nullable=True)
    visibility = db.Column(db.String(32), nullable=False, default="both", index=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
```

Even with this table, every privileged referral action should still write `AdminAuditEvent`.

## Status Lifecycle

Recommended statuses:

- `draft`: source is preparing a referral; target cannot see it.
- `sent`: referral is visible to the target structure.
- `viewed`: target has opened/read the referral.
- `accepted`: target accepts coordination responsibility.
- `rejected`: target rejects with a reason.
- `cancelled`: source revokes before target accepts.
- `expired`: system closes an unaccepted referral after `expires_at`.
- `converted`: target created a local request/case from the accepted referral.
- `closed`: no further action is expected.

Allowed transitions:

- `draft -> sent`
- `sent -> viewed`
- `sent/viewed -> accepted`
- `sent/viewed -> rejected`
- `sent/viewed -> cancelled`
- `sent/viewed -> expired`
- `accepted -> converted`
- `accepted/converted/rejected/cancelled/expired -> closed`

Do not allow `rejected`, `cancelled`, `expired`, `converted`, or `closed` to move back to
active states without a new referral.

## Federation Boundary Rules

- Source structure can list referrals where `source_structure_id == current_structure_id`.
- Target structure can list referrals where `target_structure_id == current_structure_id`
  and `status != draft`.
- Global superadmin may inspect referrals for governance, but UI/API should make this an
  explicit platform-admin path, not a normal operational view.
- Source sees the shared payload it sent, target organization identity, status, timestamps,
  and target response metadata. Source does not see target's local case unless target
  explicitly sends back a limited response.
- Target sees only `shared_payload_json`, source identity, status, consent basis, reason,
  and referral timeline. Target does not receive automatic joins to source `Request`,
  source `Case`, `CaseEvent`, `CaseParticipant`, `Assignment`, or internal notes.
- Accepted referral does not create `CaseCollaborator` automatically.
- Conversion creates a new target-owned `Request` and optional target-owned `Case`; the new
  objects use `target_structure_id` and do not point operational screens at source tenant
  data except through referral metadata.
- All state-changing actions require `ops`, `admin`, or `superadmin`. `readonly` can view
  in-scope referrals but cannot create, accept, reject, cancel, convert, or close them.
- All denied cross-tenant access attempts should be logged.
- No endpoint should accept an arbitrary `structure_id` and then return tenant records
  without checking source/target membership against the active actor scope.

## Workflow Proposal

### Create referral

1. Actor opens a source request/case within their own structure scope.
2. Service verifies actor role is mutating-capable.
3. Service verifies the source object belongs to `current_structure_id` unless global
   admin governance path is explicitly used.
4. Actor selects target structure, referral category, consent basis, and allowed fields.
5. Service creates `draft` or `sent` referral with `shared_payload_json`.
6. Write `AdminAuditEvent` and an optional source `CaseEvent`/`RequestActivity` entry.

### Receive referral

1. Target inbox query filters by `target_structure_id == current_structure_id`.
2. Draft referrals are excluded.
3. Opening a sent referral can transition `sent -> viewed` and writes audit.
4. The detail view renders only the snapshot, not joined source records.

### Accept referral

1. Target actor with `ops`, `admin`, or `superadmin` accepts.
2. Service verifies target scope and active status.
3. Status becomes `accepted`, with `decided_by_admin_id` and `decided_at`.
4. Source can see accepted status, but not target internal notes or future local case data.

### Reject referral

1. Target actor rejects with a required reason.
2. Status becomes `rejected`.
3. Source sees status and rejection category/note if marked shareable.
4. Audit records actor, structure, old/new status, and reason category.

### Convert accepted referral

1. Target actor chooses "create local request/case".
2. Service creates a new `Request` scoped to target structure from the approved snapshot.
3. Optional `Case` is created with target structure and target-local status.
4. Referral stores `target_request_id` and/or `target_case_id`; status becomes `converted`.
5. No source request/case fields are copied beyond the snapshot contract.

### Close referral

Closing marks the referral inactive after outcome handling. It should be allowed for the
owning side of the current outcome: source can close cancelled/rejected/expired; target can
close accepted/converted after local handling.

### Revoke/cancel referral

Source can cancel `sent` or `viewed` referrals before acceptance. Cancellation must not
delete the referral. It changes status to `cancelled`, writes audit, and remains visible to
both sides as an immutable coordination record.

## Service-Layer Boundary Functions

Keep all write logic behind a service module, for example
`backend/helpchain_backend/src/services/referrals.py`.

Suggested functions:

- `create_referral(actor, source_request_id=None, source_case_id=None, target_structure_id, payload, consent)`
- `list_outgoing_referrals(actor, filters)`
- `list_incoming_referrals(actor, filters)`
- `get_referral_for_actor(actor, referral_id)`
- `mark_referral_viewed(actor, referral_id)`
- `accept_referral(actor, referral_id)`
- `reject_referral(actor, referral_id, reason)`
- `cancel_referral(actor, referral_id, reason)`
- `convert_referral_to_request(actor, referral_id)`
- `close_referral(actor, referral_id)`

These functions should centralize:

- actor role checks
- source/target structure checks
- allowed status transitions
- shared payload validation
- audit writes
- transaction boundaries

Routes should be thin wrappers around the service.

## Route/API Outline

Admin web routes:

- `GET /admin/referrals/outgoing`
- `GET /admin/referrals/incoming`
- `GET /admin/referrals/<id>`
- `POST /admin/requests/<request_id>/referrals`
- `POST /admin/cases/<case_id>/referrals`
- `POST /admin/referrals/<id>/accept`
- `POST /admin/referrals/<id>/reject`
- `POST /admin/referrals/<id>/cancel`
- `POST /admin/referrals/<id>/convert`
- `POST /admin/referrals/<id>/close`

API routes can mirror these later, but should not be introduced until the service layer and
tests are stable. API mutations must write the same audit events as admin mutations.

## Migration Considerations

- Phase 1 should add tables only; do not alter `requests`, `cases`, `admin_users`, or
  `structures`.
- Keep `source_request_id` and `source_case_id` nullable to support request-only and
  case-backed flows, but require at least one with a check constraint where supported.
- Keep `target_request_id` and `target_case_id` nullable until conversion.
- Use string statuses to match existing HelpChain model style.
- Store shared data as JSON text initially for SQLite/Postgres compatibility already seen in
  the codebase; consider JSONB later only if analytics demand it.
- Backfill is not required because referrals are a new concept.
- Avoid using `CaseCollaborator` as migration seed data. A collaborator is not equivalent to
  a referral.

## Test Plan

Service tests should come first:

- source can create referral only for a request/case in its structure
- target can list only incoming non-draft referrals
- source can list only outgoing referrals
- unrelated structure receives 404/empty results, not 403 with leaked existence
- readonly cannot create, accept, reject, cancel, convert, or close
- target acceptance/rejection requires target scope
- source cancellation fails after acceptance
- conversion creates target-scoped request/case only
- shared payload excludes internal notes, participants, assignments, and full source record
- every mutation writes `AdminAuditEvent`
- denied mutation writes denied-action audit/security event
- expired referrals cannot be accepted

Route tests should cover:

- admin and ops can mutate in scope
- readonly can view in-scope referrals only
- global superadmin behavior is explicit and separately tested
- no cross-tenant list leakage in incoming/outgoing pages
- conversion does not expose source case detail URLs to target users

## Security and Privacy Risks

- Tenant leakage through detail routes that fetch by `id` before source/target scope checks.
- List leakage through counts, filters, pagination totals, or search/autocomplete across
  structures.
- Over-sharing through naive serialization of `Request`, `Case`, `CaseEvent`,
  `CaseParticipant`, `Assignment`, `ProfessionalLead`, or internal notes.
- Consent ambiguity when contact details, precise addresses, medical/social context, or
  vulnerable-person identifiers are included in the snapshot.
- Confusing `CaseCollaborator` with referral acceptance, which could accidentally grant
  broad cross-tenant case visibility.
- Audit gaps if API and admin routes mutate through different paths.
- Retention drift if referrals preserve shared snapshots longer than source requests/cases.
- Enumeration risk if target structure IDs are exposed through public forms or searchable
  endpoints without permission checks.

Mitigations:

- Return 404 for inaccessible referral IDs unless the actor is an explicit global admin.
- Use an allowlist serializer for `shared_payload_json`.
- Require a `consent_basis` and optional `consent_note` before sending.
- Keep source and target local records separate.
- Audit old/new status, actor, actor role, source/target structure IDs, and source/target
  object IDs for every mutation.
- Define retention policy before production enablement.

## Implementation Roadmap

### Phase 1: model, migration, service tests

- Add `OrganizationReferral` and optional `OrganizationReferralEvent`.
- Add service-layer functions and strict status transition logic.
- Add allowlist shared-payload serializer.
- Add service tests for tenant boundaries, roles, lifecycle, and audit.
- No UI required.

### Phase 2: admin/operator workflows

- Add outgoing and incoming admin views.
- Add send referral action from request/case detail.
- Add accept/reject/cancel/convert/close actions.
- Keep readonly view-only.

### Phase 3: audit and notifications

- Normalize `AdminAuditEvent` action names such as:
  - `referral.created`
  - `referral.sent`
  - `referral.viewed`
  - `referral.accepted`
  - `referral.rejected`
  - `referral.cancelled`
  - `referral.expired`
  - `referral.converted`
  - `referral.closed`
- Add notification jobs for target incoming referral and source decision updates.
- Add monitoring for denied cross-tenant attempts and expired referrals.

### Phase 4: federation/network layer

- Add structure network/partnership metadata if referrals should be limited to approved
  organization pairs.
- Add signed external federation events only after internal referral semantics are stable.
- Consider remote organization identifiers, idempotency keys, and delivery receipts.
- Keep the same sealed snapshot and audit principles for external federation.

## Open Decisions

- Should target structures be globally searchable by all operators, or limited to approved
  network partners?
- Which consent bases are valid for the first jurisdictional deployment?
- What exact fields are allowed in the first `shared_payload_json` contract?
- Should accepted referrals always convert to a target `Request`, or can they remain a
  coordination-only record?
- What retention period applies to rejected/cancelled/expired referral snapshots?

