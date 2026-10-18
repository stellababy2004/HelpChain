# Tenant Model

## Purpose

HelpChain is a multi-tenant coordination platform.

Each structure represents an organizational tenant boundary. Operational data belonging to one structure is isolated from users attached to another structure unless the authenticated actor has explicit platform-global access.

## Core tenant concepts

### Structure

A structure is the main organizational and tenant boundary.

Examples:

- municipality
- CCAS
- association
- social coordination service
- institutional pilot structure

A structure can scope:

- users
- services
- requests
- cases
- assignments
- notifications
- operational indicators
- dashboards
- access permissions

### Service

A service is an internal team or operational unit inside a structure.

Examples:

- action sociale
- coordination seniors
- logement
- aide alimentaire
- cellule psychologique
- terrain / intervention

## Actor scope

Authenticated administrative actors have a tenant scope derived from their role and structure attachment.

A platform-global actor requires both:

- role `superadmin`;
- no attached `structure_id`.

A `superadmin` attached to a structure is not platform-global and remains tenant-scoped.

Roles such as `admin` and `ops` do not gain cross-tenant access merely from their administrative role.

Inactive accounts are not resolved as authenticated administrative actors.

## Tenant isolation rule

For non-global actors, operational access is constrained to the actor's own `structure_id`.

When a requested resource belongs to another structure, authorization must deny or hide that resource according to the route semantics.

Platform-global actors may operate across structures where the relevant policy permits it.

## Protected operational scope

Tenant isolation is enforced across sensitive operational areas including:

- requests and request mutations;
- cases;
- assignments and intervenant access;
- notifications;
- operational dashboards and KPIs;
- organization user management;
- referrals;
- operational data exports.

Global analytics and professional-lead access require founder/platform-global authorization rather than a structure-bound administrative role.

## Authorization principle

HelpChain does not treat the `superadmin` role alone as sufficient for platform-global access.

The effective global-access invariant is:

`authenticated + superadmin + platform-global`

Platform-global status is derived from a `superadmin` actor having no attached structure.

This prevents a structure-bound `superadmin` from automatically receiving access to other tenants.

## Verification

Tenant boundaries are protected by automated authorization and regression tests.

The targeted tenant/security regression suite was verified on 18 October 2026:

- 69 tests collected;
- 69 tests passed;
- 0 tests failed.

The suite covers policy invariants and cross-tenant scenarios across operational resources.

## Product principle

Tenant isolation is a security boundary of HelpChain, not only a user-interface convention.

This allows multiple organizations to use the platform while keeping their operational data logically separated, except where explicit platform-global authorization applies.

This boundary supports institutional trust, privacy governance and GDPR-oriented operation.
