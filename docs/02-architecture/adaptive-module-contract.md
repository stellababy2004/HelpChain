# Adaptive Module Contract

**Status:** CURRENT / SOURCE OF TRUTH — CURRENT IMPLEMENTATION

This document explains how optional product modules affect route availability, tests and authorization in HelpChain.

## Why modules are explicit

HelpChain is tenant-scoped. A structure may have access to a product capability without receiving access to every operational workflow. Module activation is therefore part of the runtime contract, not only a UI preference.

The relevant checks are evaluated before the route's role-specific authorization check.

## Current module examples

| Module | Main responsibility | Typical routes |
|---|---|---|
| `cases` | Operational Case workflow built on the Request/Case spine | `/admin/cases`, case detail and case actions |
| `professionals` | Professional/intervenant workflows and related platform operations | `/admin/professional-leads` and professional workflows |

The exact route list remains subject to the route guards and focused tests in the repository.

## HTTP behavior

The distinction below is intentional:

- **404 Not Found** — the route is implemented, but the required adaptive module is not enabled for the current structure or context. This is fail-closed module behavior and avoids exposing an unavailable product surface.
- **403 Forbidden** — the module is available, but the authenticated identity does not have the required role or permission.
- **200/3xx** — the module is available and the identity is authorized for the requested operation.

Consequently, a test expecting a role-specific `403` must enable the relevant module first. Otherwise the module guard correctly returns `404` before role authorization is evaluated.

## Canonical testing rule

Fixtures must declare the product capability they are testing:

- Case lifecycle, assignment and case detail tests use a structure with the `cases` module enabled.
- Professional role and access tests use a structure with the `professionals` module enabled.
- Module-disabled tests deliberately omit the module and assert the fail-closed `404` behavior.

Do not weaken route guards or change a `404` to a `403` merely to satisfy a fixture that omitted the required module.

## Relationship to the operational model

The canonical operational spine remains:

```text
Request → Case → Assignment
```

Module availability controls whether a structure can use a particular part of that spine. It does not replace tenant isolation, RBAC or explicit referral boundaries. Those checks remain independently required.

## Evidence and maintenance

When this contract changes, update the relevant route guard, focused tests and fixture definitions together. Use the current implementation and tests as the final authority if this document conflicts with runtime behavior.
