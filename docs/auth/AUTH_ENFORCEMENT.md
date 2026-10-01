# HelpChain — Auth Enforcement Rules

## Canonical login families

### 1. Volunteer

- Canonical public entry route: `/become_volunteer`
- Legacy/dev route: `/volunteer_login`
- Volunteer onboarding routes: `/become_volunteer`, `/volunteer_register`
- Protected volunteer pages rely on `volunteer_id` in session
- Volunteers must never use admin login routes
- Volunteers must never access admin-only pages
- Volunteer auth is session-based and does NOT use Flask-Login

### 2. Admin family
- Canonical login route: `/admin/login`
- Alias route: `/admin/ops/login`
- Admin-family users authenticate through `AdminUser`
- Admin-family users must never use volunteer login flows

### 3. Professional
- Current state: approval-based onboarding only
- No dedicated professional login flow yet
- Professionals must not use volunteer login routes
- Professionals must not use admin login routes unless they are separately provisioned as AdminUser

## Redirect rules

- Unauthenticated access to admin-only pages must redirect to `/admin/login`
- Unauthenticated access to volunteer-only pages must redirect to `/become_volunteer` or `/volunteer_login` according to current volunteer flow
- Admin login success must redirect by role:
  - `superadmin` -> `admin_home`
  - `admin` -> `admin_pilotage`
  - `ops` -> `admin_operator_dashboard`
  - `readonly` -> restricted admin area
- Volunteer login success must redirect to volunteer area only

## Separation rules

- `Volunteer` and `AdminUser` are separate auth families
- `ProfessionalLead` is not an authenticated actor
- `Intervenant` is currently an approved operational entity, not a standalone login family
- `User` must not be used implicitly as a fallback auth source without explicit policy