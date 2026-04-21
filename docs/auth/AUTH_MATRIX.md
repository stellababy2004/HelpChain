# HelpChain — Auth Matrix (Canonical)

## 1. Volunteer

- Model: Volunteer
- Canonical public entry: /become_volunteer
- Legacy/dev entry: /volunteer_login
- Protected volunteer session: volunteer_id (session-based, not Flask-Login)
- Auth method: email / confirmation / magic-link style flow
- Created by: self (external actor)
- Post-login redirect: /volunteer/dashboard
- Notes: completely separate from admin auth system

---

## 2. Admin family (internal)

- Model: AdminUser
- Canonical login: /admin/login
- Alias: /admin/ops/login
- API auth: /api/auth/login
- Auth method: password + session
- MFA: required for superadmin, recommended for admin/ops
- Created by: internal provisioning only
- Manual approval: yes (not public)
- Post-login (role-based):
  - superadmin → admin_home
  - admin → admin_pilotage
  - ops → admin_operator_dashboard
  - readonly → restricted admin views

---

## 3. Professional (current canonical state)

- Lead model: ProfessionalLead
- Approved operational actor: Intervenant
- Public/business entry: professional access request
- Review surface: /admin/pro-access/*
- Auth method: no dedicated professional login yet
- Created by: external request + internal admin review
- Manual approval: required
- Post-approval result: operational record (Intervenant), not yet a standalone login account
- Notes: professional onboarding exists; professional authentication is not yet implemented as a separate actor login flow

---

## 4. Generic User (to clarify)

- Model: User
- Status: unclear / possibly legacy
- Action: audit and decide if deprecated or reused

---

## 5. User (legacy/general domain model)

- Model: User
- Status: legacy/general operational model
- Canonical auth family: none
- Current usage: domain references, compatibility paths, case/user relationships, push subscriptions
- Must not be used for new authentication flows
- Notes: Admin auth uses AdminUser; volunteer flow uses Volunteer session state

## 5. Rules

- Volunteer NEVER uses admin login
- Admin NEVER uses volunteer flow
- /admin/login is canonical admin entry point
- /admin/ops/login is alias, not separate system
- Professional access is approval-based, not open signup 

## 6. User model enforcement

- `User` is not a canonical authentication family
- New login flows must not be built on top of `User`
- `User` may remain in legacy/domain relationships until explicitly migrated
- Admin authentication must use `AdminUser`
- Volunteer authentication must use the volunteer session flow