# Changelog — Analytics routing consolidation (2026-01-27)

Branch: `release/freeze-landing`  
Scope: analytics routing cleanup + removal of obsolete template dependency

## Context

We previously had a legacy `/predictive-analytics` page that attempted to render `predictive_analytics.html`.  
That template was archived during the “legacy templates” cleanup, which could lead to `TemplateNotFound`  
errors or dead-end navigation.

Goal: keep analytics UI **single-source-of-truth** and avoid stale template paths.

## Changes

### 1) Predictive analytics route now redirects to the Admin Analytics dashboard

File: `backend/analytics_routes.py`

- Updated route: `@analytics_bp.route("/predictive-analytics")`
- Behavior:
  - If not admin: keeps the existing admin guard behavior (login redirect / message)
  - If admin: **redirects to** `url_for("analytics_bp.admin_analytics")`
- Result:
  - Removes dependency on `predictive_analytics.html`
  - Consolidates analytics UI under the existing admin dashboard

### 2) Analytics root route normalized (admin-only redirect)

File: `backend/analytics_routes.py`

- Updated route: `@analytics_bp.route("/")`
- Behavior:
  - Enforces admin-only access via `@require_admin_login`
  - Redirects to `url_for("analytics_bp.admin_analytics")`
- Result:
  - Removes duplicated session checks / debug prints
  - Ensures consistent access policy across analytics endpoints

## Verification checklist

- [ ] Restart the Flask app
- [ ] Visit `/` (analytics root) → should redirect to admin analytics dashboard (or to admin login if not authenticated)
- [ ] Visit `/predictive-analytics` → should redirect to admin analytics dashboard (or to admin login if not authenticated)
- [ ] Confirm no runtime dependency remains on `predictive_analytics.html`

## Notes

This change is intentionally conservative:
- No UI template changes
- No DB changes
- Only routing behavior is adjusted to prevent template-missing failures
