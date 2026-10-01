# Tenant-scoped website analytics

Conversion Engine remains at `/admin/conversion-dashboard`. Admin and ops actors
see only the `structure_id` loaded from their active database account. The existing
`can_view_global_analytics` policy continues to grant superadmins global visibility
(including structure-attached superadmins, as required by the existing policy).
No frontend parameter, session role string, or ambient `g.structure_id` grants scope.

The same boundary covers the funnel, revenue intelligence, alerts, alert dispatch,
and tracking configuration. Conflicting tenant selectors return 403. Global admins
can select a site with `?site_id=<structure-slug>`; the dashboard carries this filter
to every panel. API responses include `scope`; the page labels the organization/site.
Revenue sessions and persisted explanations are namespaced by tenant.

## Data and migration

`AnalyticsEvent.structure_id` references the existing `Structure`. There is no new
organization or site model: `Structure.slug` is the unique public site identifier.
Every newly ingested event is assigned a structure on the server. The first-party
HelpChain collector, page-view feed, and legacy analytics service use the existing
deployment-owned `HC_DEFAULT_STRUCTURE_SLUG` (default: `default`). They do not infer
ownership from a visitor's identity or a submitted URL.

Migration `20261001_1000` adds the nullable foreign key and index. Apply it through
the normal release process **before running the updated application**. This work
does not apply the migration to any application database. Historical NULL rows
remain visible only in global analytics; there is no speculative backfill. Existing
global audience/revenue surfaces retain their existing authorization policy.
Legacy unscoped data/bookmark/stream endpoints on the analytics blueprint are
restricted to the same global analytics policy.

## Integrating any organization's external website

1. Use an existing HelpChain structure with a unique slug. An organization admin/ops
   user requests `GET /admin/api/website-tracking` while authenticated. A global
   admin must select `?site_id=<slug>` (or `?structure_id=<id>`).
2. The response contains `site_id`, `ingestion_key`, and endpoint
   `/api/website/events`. Store both settings in the **website backend**, keeping
   the key secret. Configuration responses have `Cache-Control: private, no-store`.
3. The website browser reports page views and clicks to its own backend. That
   backend validates/rate-limits its public collector and forwards allowed events
   to HelpChain over HTTPS. Send successful form submissions from the backend
   after accepting the form. No direct cross-origin browser integration or CORS
   configuration is required.

Example request from the external website backend:

```http
POST /api/website/events
Content-Type: application/json
X-Analytics-Key: <server-side-ingestion-key>

{
  "site_id": "your-structure-slug",
  "event": "page_view",
  "page_url": "/programmes",
  "session_id": "opaque-visitor-session"
}
```

Supported events: `page_view`, `cta_click`, `form_submit`. `page_url` must start
with `/` and contain at most 500 characters. Query strings/fragments are discarded.
`session_id` is optional and at most 128 characters. Use an opaque random value;
do not forward names, email addresses, form contents, or authentication cookies.
The external collector does not store raw IPs or user agents.

Successful storage returns 201 with `{"ok": true}`. Missing/invalid site IDs or
credentials, mismatched site/key pairs, and conflicting tenant parameters return
403. Malformed events return 400. Both the numeric structure ID and current slug
are signed using the application's existing secret with a dedicated signing salt;
they are checked against the current database record. Knowing another site's
public slug does not authorize writes. An authenticated organization actor cannot
use another tenant's credential, either. A stolen backend credential is a secret
compromise; do not embed it in JavaScript or treat Origin/Referer as authentication.
Changing the structure slug invalidates its old credentials; rotating the app
secret invalidates all ingestion credentials. There is no independent key-rotation
storage in this minimal implementation.

The existing `/events` endpoint remains the public **HelpChain first-party**
collector and retains its traffic exclusions and existing payload contract.
Payloads selecting a tenant are routed through credential validation; it cannot
be used to bypass external website authentication. Missing-ID rejection applies
to `/api/website/events`, not the backward-compatible first-party collector.

No deployment configuration, production data, or external notifications are
created by this implementation or its tests.
