# RBAC Matrix

## Purpose

This document defines the role-based access model used by HelpChain.

Authorization combines role-based permissions with tenant/structure scope. A role alone does not automatically grant cross-tenant access.

## Main roles

| Role | Purpose | Typical access |
|---|---|---|
| superadmin (platform-global) | Platform-level administration | Cross-structure access where platform-global policies permit it |
| superadmin (structure-bound) | Privileged structure administration | Restricted to the attached structure; not automatically platform-global |
| admin | Structure-level administration | Manage permitted operational resources within the attached structure |
| ops | Operational queue handling | Daily treatment of permitted requests, cases, assignments and follow-up within tenant scope |
| readonly | Observation and reporting | View-only access where explicitly supported by the relevant route or feature |

## Platform-global invariant

The `superadmin` role alone is not sufficient for global access.

Platform-global access requires:

`authenticated + role=superadmin + structure_id=None`

A `superadmin` with a `structure_id` remains structure-bound.

Founder/global capabilities such as global analytics and professional-lead access require platform-global authorization.

## Tenant scope

For non-global administrative actors:

- access is constrained to the actor's attached structure;
- cross-tenant resources are denied or hidden according to route semantics;
- exports must respect the same tenant boundary as interactive views;
- administrative role names do not override tenant isolation.

An inactive admin account is not resolved as an authenticated administrative actor.

## Access principles

- Platform-global superadmin access is exceptional.
- Structure-bound superadmins do not automatically receive cross-tenant access.
- Admin access is tenant-scoped.
- Ops access is tenant-scoped and focused on operational workflows.
- Readonly access must not be assumed unless explicitly implemented by the relevant feature.
- Sensitive operations should remain traceable through audit/activity mechanisms.

## Protected areas

| Area | platform-global superadmin | structure-bound superadmin | admin | ops |
|---|---:|---:|---:|---:|
| Own-structure operational data | yes | yes | yes | permitted operational scope |
| Other tenants' operational data | permitted by global policy | no | no | no |
| Global analytics | yes | no | no | no |
| Professional leads / founder-global area | yes | no | no | no |
| Requests and cases | cross-tenant where permitted | own structure | own structure | own permitted scope |
| Operational exports | cross-tenant where permitted | own structure | own structure | own permitted scope |
| Organization user management | platform policy | own structure where permitted | own structure where permitted | restricted |
| Platform-global settings | yes | no | no | no |

## MFA principle

Privileged administrative access should use MFA where required by platform policy.

MFA does not replace authorization: successful authentication does not grant access outside the actor's role and tenant scope.

## Verification

The authorization model is protected by automated policy and regression tests.

On 18 October 2026, the targeted tenant/security regression suite completed with:

- 69 tests passed;
- 0 tests failed.

The verified scenarios include platform-global invariants and cross-tenant restrictions across requests, cases, assignments, notifications, exports, referrals and organization user management.

## Security principle

HelpChain applies both RBAC and tenant scoping.

In practical terms:

`effective access = authenticated actor + permitted role + permitted tenant scope`

This matrix is a security reference. Route guards and regression tests remain the source of truth for implemented authorization behavior.
