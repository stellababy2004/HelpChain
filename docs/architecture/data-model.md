# HelpChain Canonical Data Model

## 1. Purpose of the Data Model

HelpChain is a **multi-tenant social coordination infrastructure**, not a volunteer marketplace.  
The data model must support structured, traceable, and accountable coordination across territorial actors (structures, professionals, associations, municipalities).

This document defines the **canonical target model** and highlights what already exists vs what should be refactored.

## 2. Core Canonical Entities

- Structure
- AdminUser
- Request
- Intervenant (Actor)
- Assignment
- AdminAuditEvent

## 3. Entity Descriptions

### Structure
**Represents** the tenant boundary (organization / structure / territory).  
**Why it exists**: it is the isolation unit for data, access control, and operational metrics.

Likely fields:
- `id`
- `name`
- `slug`
- `status`
- `territory`
- `created_at`

### AdminUser
**Represents** authenticated platform users with operational or administrative roles.  
**Why it exists**: admin/operators are the primary actors for managing requests and governance.

Likely fields:
- `id`
- `username`
- `email`
- `role`
- `structure_id`
- `is_active`

### Request
**Represents** the core operational object (a social situation to coordinate).  
**Why it exists**: requests are the primary unit of work tracked across the platform.

Likely fields:
- `id`
- `structure_id`
- `title`
- `description`
- `status`
- `priority`
- `category`
- `city`
- `created_at`
- `updated_at`
- `owner_id` (or `assigned_to_user_id`)
- `closed_at`

### Intervenant (Actor)
**Represents** any person or organization that can intervene in a request.  
**Why it exists**: HelpChain must unify multiple actor types under one operational concept.

This replaces the narrow “volunteer-only” framing.

Actor types can include:
- bénévole
- professionnel
- association
- service municipal
- travailleur social

Likely fields:
- `id`
- `structure_id`
- `name`
- `actor_type`
- `email`
- `phone`
- `location`
- `is_active`
- `created_at`

### Assignment
**Represents** the relationship between a Request and an Intervenant.  
**Why it exists**: assignments should be explicit, traceable, and support multiple actors.

Likely fields:
- `id`
- `request_id`
- `actor_id`
- `assigned_by_admin_id`
- `assigned_at`
- `status`
- `notes`

### AdminAuditEvent
**Represents** the audit trail for privileged actions.  
**Why it exists**: institutions require traceability (“who did what, when”).

Fields:
- `id`
- `admin_user_id`
- `admin_username`
- `action`
- `target_type`
- `target_id`
- `payload`
- `ip`
- `user_agent`
- `created_at`

## 4. Structure as Tenant Boundary

The **Structure** entity is the tenant boundary.  
All requests, admin users, actors, and assignments are scoped by `structure_id`.

## 5. AdminUser Role Model

Roles should remain minimal and operational:
- Global admin: platform-wide governance
- Structure admin: scoped to a single structure
- Operator: operational execution
- Readonly: view-only operator role

`structure_id` is the canonical scoping key for AdminUser.

## 6. Request is the Core Object

Requests represent the full lifecycle of a social situation:
signalement → qualification → coordination → suivi.

Requests should be:
- scoped to a structure
- traceable
- assignable to multiple actors

## 7. Intervenant / Actor Direction

The canonical model must replace **volunteer-only** concepts with a unified **Intervenant** model.  
This ensures the platform can represent:
professionals, associations, municipal services, and volunteers under one system.

## 8. Operational ownership vs assignment

- owner_id represents the current internal operational owner of a Request.
- Assignment represents broader intervention relationships and historical accountability.

## 8. Assignment as a First-Class Concept

Assignments should not be limited to a single `owner_id` on Request.  
They should be modeled explicitly so that:
- multiple actors can be assigned
- assignment history is auditable
- responsibilities are traceable

## 9. AdminAuditEvent for Traceability

AdminAuditEvent provides governance-level traceability and is a cornerstone for enterprise trust.

## 10. Relationship Overview

Structure
- has many AdminUsers
- has many Requests
- has many Intervenants
- defines tenant scope for audit context

Request
- belongs to Structure
- may have one owner
- may have many Assignments
- generates AdminAuditEvents
- generates operational alerts (computed)

Intervenant
- belongs to Structure
- may participate in many Requests (via Assignment)

## 11. Existing vs Target Model

**Already exists in codebase**
- `Structure`
- `AdminUser` with `structure_id`
- `Request`
- `AdminAuditEvent`
- `Volunteer` (legacy actor concept)
- `ProfessionalLead` (professional dataset)

**Target architecture (not fully implemented)**
- Unified `Intervenant` model
- Explicit `Assignment` model
- Migration of “volunteer-only” UI/routes to actor-based workflows

**Refactor direction**
- Replace `/admin/volunteers` with `/admin/intervenants`
- Align UI labels and routes with actor-based language
- Treat “volunteer” as one `actor_type` rather than a primary model

## 13. Non-canonical / legacy concepts

- **Volunteer** → legacy, to be absorbed into Intervenant (ctor_type=volunteer).
- **ProfessionalLead** → pre-operational / acquisition dataset, not canonical operational core.

## 12. Architectural Guidance

- The current `/admin/volunteers` screen is **not** canonical long-term.
- Future refactors should move toward `/admin/intervenants`.
- UI, routes, and data semantics should align with the canonical model in this document.

## 14. Migration strategy

Phase A: UI rename and conceptual refactor.
Phase B: route cleanup.
Phase C: data model convergence toward Intervenant + Assignment.

This document is the **reference point** for future HelpChain refactors.
