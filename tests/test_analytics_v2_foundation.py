import json
from datetime import timedelta

from backend.models import AdminUser, Structure, utc_now
from backend.models_with_analytics import AnalyticsEvent, UserBehavior
from backend.helpchain_backend.src.services.analytics_v2 import (
    ANALYTICS_SCOPE_PLATFORM_SALES,
    ANALYTICS_SCOPE_TENANT,
)
from backend.helpchain_backend.src.services.website_analytics import ingestion_token


PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Forwarded-For": "203.0.113.55",
}


def _login(client, app, admin):
    with client.session_transaction() as sess:
        sess.update({
            "_user_id": str(admin.id),
            "admin_user_id": admin.id,
            "admin_id": admin.id,
            "user_id": admin.id,
            "role": admin.role,
            "admin_logged_in": True,
            "is_admin": True,
            "is_authenticated": True,
            "mfa_required": True,
            "mfa_ok": True,
            "mfa_ok_until": (utc_now() + timedelta(minutes=30)).isoformat(),
            "admin_mfa_last_verified": 4102444800,
            "admin_mfa_user_id": admin.id,
        })
        sess[app.config.get("MFA_SESSION_KEY", "mfa_ok")] = True


def test_first_party_legacy_cta_is_canonical_and_deduped(client):
    payload = {
        "event_id": "evt_phase1_legacy_cta",
        "event": "deployment_pilot_cta_clicked",
        "props": {
            "url": "/deploiement",
            "category": "conversion",
            "cta": "hero_pilot_access",
        },
    }

    response = client.post("/events", json=payload, headers=PUBLIC_HEADERS)
    duplicate = client.post("/events", json=payload, headers=PUBLIC_HEADERS)

    assert response.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.get_json()["duplicate"] is True
    assert AnalyticsEvent.query.count() == 1
    event = AnalyticsEvent.query.one()
    assert event.event_type == "cta_click"
    assert event.analytics_scope == ANALYTICS_SCOPE_PLATFORM_SALES
    assert event.event_id == "evt_phase1_legacy_cta"
    assert event.visitor_id.startswith("vis_")
    assert event.user_session.startswith("aud_")
    assert event.user_ip is None
    props = json.loads(event.properties_json)
    assert props["original_event_type"] == "deployment_pilot_cta_clicked"
    assert props["canonical_event_type"] == "cta_click"


def test_server_page_view_uses_visitor_session_and_no_raw_ip(client):
    response = client.get("/offre", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    event = AnalyticsEvent.query.filter_by(page_url="/offre").one()
    assert event.event_type == "page_view"
    assert event.analytics_scope == ANALYTICS_SCOPE_PLATFORM_SALES
    assert event.visitor_id.startswith("vis_")
    assert event.user_session.startswith("aud_")
    assert event.user_ip is None
    behavior = UserBehavior.query.filter_by(session_id=event.user_session).one()
    assert behavior.visitor_id == event.visitor_id
    assert behavior.analytics_scope == ANALYTICS_SCOPE_PLATFORM_SALES
    assert behavior.ip_address is None


def test_external_tenant_event_gets_tenant_scope_and_canonical_form_submit(client, session):
    structure = Structure(name="Tenant Analytics", slug="tenant-analytics")
    session.add(structure)
    session.commit()

    response = client.post(
        "/api/website/events",
        headers={"X-Analytics-Key": ingestion_token(structure), **PUBLIC_HEADERS},
        json={
            "site_id": structure.slug,
            "event_id": "evt_tenant_submit",
            "event": "form_submit",
            "page_url": "/tenant-demo",
            "visitor_id": "vis_external",
            "session_id": "aud_external",
        },
    )

    assert response.status_code == 201
    event = AnalyticsEvent.query.filter_by(event_id="evt_tenant_submit").one()
    assert event.structure_id == structure.id
    assert event.analytics_scope == ANALYTICS_SCOPE_TENANT
    assert event.event_type == "form_submitted"
    assert event.visitor_id == "vis_external"
    assert event.user_session == "aud_external"


def test_platform_sales_endpoint_excludes_tenant_events(app, session):
    structure = Structure(name="Scoped Org", slug="scoped-org")
    session.add(structure)
    session.flush()

    global_admin = AdminUser(
        username="global_sales_admin",
        email="global-sales-admin@test.local",
        role="superadmin",
        structure_id=None,
        password_hash="x",
        is_active=True,
        mfa_enabled=True,
        totp_secret="phase1-secret",
    )
    session.add_all([
        global_admin,
        AnalyticsEvent(
            structure_id=structure.id,
            analytics_scope=ANALYTICS_SCOPE_TENANT,
            event_type="page_view",
            page_url="/tenant-only",
            user_session="aud_tenant",
        ),
        AnalyticsEvent(
            analytics_scope=ANALYTICS_SCOPE_PLATFORM_SALES,
            event_type="page_view",
            page_url="/offre",
            user_session="aud_platform",
        ),
    ])
    session.commit()

    global_client = app.test_client()
    _login(global_client, app, global_admin)
    response = global_client.get("/admin/api/conversion-funnel")

    assert response.status_code == 200
    data = response.get_json()
    assert data["scope"]["analytics_scope"] == ANALYTICS_SCOPE_PLATFORM_SALES
    assert data["summary"]["events"] == 1
    assert "/offre" in response.get_data(as_text=True)
    assert "/tenant-only" not in response.get_data(as_text=True)
