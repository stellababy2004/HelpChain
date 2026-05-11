# Tenant Model

## Purpose

HelpChain is designed as a multi-tenant coordination platform.

Each tenant represents an organization or structure using the platform.

## Core tenant concepts

### Structure

A structure is the main organizational boundary.

Examples:

- municipality
- CCAS
- association
- social coordination service
- institutional pilot structure

A structure can own or scope:

- users
- services
- requests
- cases
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

### User scope

Users should be attached to the structure they operate in, unless they are platform-level superadmins.

## Scoping principle

Operational data should be filtered by structure whenever a user is not a platform-level superadmin.

This protects tenant isolation and prevents accidental cross-structure visibility.

## Tenant isolation rules

| Object | Should be structure-scoped |
|---|---:|
| Requests | yes |
| Cases | yes |
| Services | yes |
| Admin users | preferably yes |
| Operators | yes |
| Notifications | yes |
| Audit/activity logs | yes when linked to tenant data |
| Global platform settings | no |

## Product principle

The tenant model allows HelpChain to serve multiple institutions without mixing their operational data.

This is essential for institutional trust, GDPR alignment and future SaaS monetization.
