# RBAC Matrix

## Purpose

This document defines the role-based access model used by HelpChain.

The goal is to keep operational access controlled, auditable and scoped by responsibility.

## Main roles

| Role | Purpose | Typical access |
|---|---|---|
| superadmin | Platform-level administration | Full access across structures and system settings |
| admin | Structure-level administration | Manage requests, cases, users and operational settings for one structure |
| ops | Operational queue handling | Daily treatment of requests, cases, assignments and follow-up |
| readonly | Observation and reporting | View operational data without modifying it |

## Access principles

- Superadmin access is exceptional and should be limited.
- Admin access should be scoped to a structure whenever possible.
- Ops users should focus on actionable queues and follow-up.
- Readonly users should never modify operational records.
- Sensitive operations should be traceable through audit/activity logs.

## Protected areas

| Area | superadmin | admin | ops | readonly |
|---|---:|---:|---:|---:|
| Admin home | yes | yes | limited | view |
| Requests | yes | yes | yes | view |
| Cases | yes | yes | yes | view |
| Operator workspace | yes | yes | yes | no/limited |
| Security panel | yes | limited | no | no |
| Roles/users | yes | limited | no | no |
| Notifications | yes | yes | limited | view |
| Revenue/leads | yes | limited | no | view/limited |
| Platform settings | yes | no/limited | no | no |

## MFA principle

Admin-grade access should require MFA when enabled.

Password-only login must not directly open privileged admin surfaces when MFA is required.

## Notes

This matrix is a product and security reference. Actual route guards should be reviewed regularly against this document.
