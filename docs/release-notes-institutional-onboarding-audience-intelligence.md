# Institutional Onboarding and Audience Intelligence Release Notes

## Release Scope

This note summarizes recent HelpChain product work across institutional onboarding, audience intelligence, revenue radar, and prospect auto-capture. It is intended for internal product and project tracking.

The release expands the founder/admin view from operational request management into a connected onboarding and prospect intelligence layer:

- Public institutional access requests can now be submitted and reviewed.
- Approved institutions can be converted into structures with a first organization admin.
- Professional leads are again available through a premium admin pipeline.
- Public audience signals are captured for selected high-intent pages.
- Anonymous audience sessions can be ranked by likely business intent and linked to later conversions.

## Institutional Onboarding - Phase 1

### What Was Added

- Public access request route at `/demander-acces`.
- `OrganizationAccessRequest` model backed by the `organization_access_requests` table.
- Admin list page for institutional access requests at `/admin/organizations/requests`.
- Admin navigation/discoverability entry for access requests in the platform administration area.

### Product Value

This creates the first formal intake path for institutions that want HelpChain access. Instead of handling requests outside the product, founder/admin users can capture organization name, contact details, organization type, estimated users, city, message, review status, and internal notes in a dedicated workflow.

## Institutional Onboarding - Phase 2

### What Was Added

- Request detail page at `/admin/organizations/requests/<id>`.
- Review actions for:
  - approve
  - reject
  - need-info
- Structure creation when an access request is approved.
- First organization admin creation on approval.
- Internal notes capture during review.
- Duplicate approval protection so re-approving an already approved request does not create additional structures.
- Review metadata including reviewer and reviewed timestamp.

### Product Value

The onboarding flow now moves beyond intake into operational conversion. A qualified request can become a tenant structure with an initial admin user, while rejected or incomplete requests remain traceable. Duplicate approval protection reduces the risk of creating accidental duplicate structures during admin review.

## Premium Professional Leads Restore

### What Was Added

- Restored `/admin/professional-leads`.
- Premium-style pipeline view for professional lead qualification.
- KPI strip for lead pipeline state, including new leads, leads to qualify, priority leads, follow-ups due, and qualified leads.
- Improved filtering by email, profession, city, and status.
- List/table and responsive card views for reviewing lead state, urgency, source, last activity, and next action.
- Detail/admin actions remain available through the professional lead admin flow.

### Product Value

Professional leads are again visible as a structured operational pipeline rather than scattered form submissions or imports. The founder/admin can scan lead volume, qualification state, and next actions from one admin surface.

## Audience France Map

### What Was Added

- Admin audience map route at `/admin/audience-map`.
- KPI strip for recent visitors, active cities, key page views, and detected intent signals.
- France-first territorial audience view with active city markers when location data is available.
- Top pages table based on recent `page_view` traffic.
- Founder intelligence section covering business-readable signals, sources, and repeated sessions.
- Graceful empty states when analytics tables or usable geo data are unavailable.

### Product Value

The founder now has an internal view of territorial and behavioral interest in HelpChain. The page is intentionally operational: it shows where interest is coming from, which pages are being viewed, and whether any repeated or high-intent behavior is emerging.

## Audience Data Feed

### What Was Added

- Server-side `page_view` ingestion for selected public pages.
- Tracked pages:
  - `/`
  - `/offre`
  - `/deploiement`
  - `/professionnels`
  - `/demander-acces`
  - `/contact`
- Reuse of existing analytics models:
  - `AnalyticsEvent`
  - `UserBehavior`
- Analytics schema migration for:
  - `analytics_events`
  - `user_behaviors`
- Defensive tracking behavior so analytics write failures do not break page rendering.

### Product Value

HelpChain can now collect lightweight first-party audience data for high-intent public pages without depending on the visitor being logged in. This data powers the audience map, revenue radar, and later conversion context.

## Revenue Radar

### What Was Added

- Anonymous session scoring based on visited pages, page count, recency, repeat behavior, and external referrer signals.
- Temperature buckets:
  - Froid
  - Tiede
  - Chaud
  - Tres chaud
- Recommended founder actions shown in the audience map.
- Founder insights summarizing current high-intent traffic.
- Session ranking by likely business intent inside the `/admin/audience-map` Revenue Radar section.

### Product Value

Revenue Radar gives the founder a prioritized view of anonymous sessions that look commercially relevant. It does not identify visitors by itself; it ranks intent signals so follow-up attention can focus on sessions that interacted with pages such as `/demander-acces`, `/deploiement`, `/offre`, `/professionnels`, or `/contact`.

## Prospect CRM Auto Capture

### What Was Added

- Linking of anonymous session history to later form submissions when the same session converts.
- Target models:
  - `OrganizationAccessRequest`
  - `ProfessionalLead`
- Attached "Audience avant conversion" intelligence in admin detail pages.
- Stored conversion context includes session score, temperature, source, first/last seen timestamps, pages viewed, key pages, repeat visit signal, and intent flags.
- Revenue Radar linkage badges for sessions already tied to an access request or professional lead.

### Product Value

The admin detail view can now show what a prospect did before converting. For example, an institutional access request can carry prior visits to `/offre`, `/deploiement`, or `/demander-acces`, making qualification more informed without requiring manual reconstruction from raw analytics rows.

## Routes / Admin Surfaces Added

- `/demander-acces` - public institutional access request page.
- `/admin/organizations/requests` - admin list of institutional access requests.
- `/admin/organizations/requests/<id>` - admin detail and review page.
- `/admin/organizations/requests/<id>/approve` - approval action.
- `/admin/organizations/requests/<id>/reject` - rejection action.
- `/admin/organizations/requests/<id>/need-info` - request-more-information action.
- `/admin/professional-leads` - restored professional leads pipeline.
- `/admin/audience-map` - audience map, founder intelligence, and Revenue Radar.

## Product Impact Summary

This work connects four previously separate concerns into one early institutional growth loop:

- Institutions can request access publicly.
- Admins can review and convert approved institutions into structures.
- Professional leads can be tracked in a restored premium pipeline.
- Audience behavior from key public pages can inform both founder-level prioritization and individual prospect review.

The result is a clearer path from anonymous interest to captured prospect to reviewed institutional onboarding.

## Deferred / Not Yet Implemented

- No automated outbound email workflow for access request approval, rejection, or need-info decisions is documented as part of this release.
- No automated password delivery or activation flow for the first organization admin is described here.
- No CRM ownership model beyond the currently visible lead/admin fields is claimed here.
- No external analytics provider integration is included in this summary.
- No claim is made that anonymous sessions identify real-world organizations before a form submission.
- No schema changes beyond the implemented access request and analytics migrations are implied.

## Recommended Next Priorities

- Add explicit operator/founder playbook steps for reviewing access requests and acting on Revenue Radar sessions.
- Add a safe activation or invitation flow for the first organization admin created during approval.
- Add lightweight status history or audit visibility for access request review decisions if deeper traceability is needed.
- Define how professional leads and organization access requests should converge or remain separate in the product model.
- Add a retention/privacy note for audience session intelligence attached to prospect records.

## One-Line Product Summary

HelpChain now has a connected internal path from France-first audience signals to prospect capture, institutional review, and structure onboarding.
