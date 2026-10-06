from datetime import timedelta

import pytest
from flask import g

from backend.models import AdminUser, Structure, utc_now
from backend.models_with_analytics import AnalyticsEvent
from backend.helpchain_backend.src.services.website_analytics import ingestion_token


READ_ENDPOINTS = (
    "/admin/api/conversion-funnel",
    "/admin/api/revenue-intelligence",
    "/admin/api/revenue-alerts",
)


def login(client, app, admin):
    with client.session_transaction() as sess:
        sess.update({
            "_user_id": str(admin.id), "admin_user_id": admin.id,
            "admin_id": admin.id, "user_id": admin.id,
            "role": admin.role, "admin_logged_in": True,
            "is_admin": True, "is_authenticated": True,
            "mfa_required": True, "mfa_ok": True,
            "mfa_ok_until": (utc_now() + timedelta(minutes=30)).isoformat(),
            "admin_mfa_last_verified": 4102444800, "admin_mfa_user_id": admin.id,
        })
        sess[app.config.get("MFA_SESSION_KEY", "mfa_ok")] = True


@pytest.fixture
def tenants(app, session, monkeypatch):
    # Never send real notifications during integration tests.
    monkeypatch.delenv("HC_REVENUE_ALERT_SLACK_WEBHOOK", raising=False)
    monkeypatch.delenv("HC_REVENUE_ALERT_EMAIL_TO", raising=False)
    from backend.helpchain_backend.src.routes.analytics import _SENT_REVENUE_ALERTS
    _SENT_REVENUE_ALERTS.clear()
    a = Structure(name="Organization A", slug="analytics-a", website="https://a.example")
    b = Structure(name="Organization B", slug="analytics-b", website="https://b.example")
    session.add_all([a, b])
    session.flush()
    users = {}
    for name, role, structure in (
        ("admin", "admin", a), ("ops", "ops", a),
        ("global", "superadmin", None), ("unscoped", "admin", None),
    ):
        users[name] = AdminUser(
            username=f"website_{name}", email=f"website-{name}@test.local",
            role=role, structure_id=structure.id if structure else None,
            password_hash="x", is_active=True, mfa_enabled=True,
            totp_secret="website-analytics-test-secret",
        )
        session.add(users[name])
    for structure in (a, b):
        for event_type in ("page_view", "cta_click", "form_submit"):
            session.add(AnalyticsEvent(
                structure_id=structure.id, event_type=event_type,
                user_session="same-session", page_url=f"/{structure.slug}",
            ))
    session.add(AnalyticsEvent(event_type="page_view", page_url="/legacy-unassigned"))
    session.commit()
    return {"a": a, "b": b, "users": users, "key_a": ingestion_token(a), "key_b": ingestion_token(b)}


@pytest.mark.parametrize("role", ["admin", "ops"])
@pytest.mark.parametrize("endpoint", READ_ENDPOINTS)
def test_organization_reads_only_own_events(app, client, tenants, role, endpoint):
    login(client, app, tenants["users"][role])
    response = client.get(endpoint)
    assert response.status_code == 200
    data = response.get_json()
    assert data["scope"]["structure_id"] == tenants["a"].id
    assert "analytics-b" not in response.get_data(as_text=True)
    assert "legacy-unassigned" not in response.get_data(as_text=True)
    assert "analytics-a" in response.get_data(as_text=True)
    if "summary" in data:
        assert data["summary"]["events"] == 3
        assert data["summary"]["form_submits"] == 1


@pytest.mark.parametrize("endpoint", (*READ_ENDPOINTS, "/admin/conversion-dashboard", "/admin/api/website-tracking"))
@pytest.mark.parametrize("selector", ["structure_id", "organization_id", "site_id", "tracking_id"])
def test_direct_foreign_tenant_selection_is_forbidden(app, client, tenants, endpoint, selector):
    login(client, app, tenants["users"]["admin"])
    value = tenants["b"].slug if selector in {"site_id", "tracking_id"} else tenants["b"].id
    assert client.get(endpoint, query_string={selector: value}).status_code == 403


@pytest.mark.parametrize("endpoint", READ_ENDPOINTS)
def test_global_admin_can_read_all_and_select_one_site(app, client, tenants, endpoint):
    login(client, app, tenants["users"]["global"])
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.json["scope"]["structure_id"] is None
    assert "analytics-a" in response.get_data(as_text=True)
    assert "analytics-b" in response.get_data(as_text=True)
    selected = client.get(endpoint, query_string={"site_id": tenants["b"].slug})
    assert selected.status_code == 200
    assert "analytics-a" not in selected.get_data(as_text=True)
    assert selected.json["scope"]["structure_id"] == tenants["b"].id
    if "summary" in response.json:
        assert response.json["summary"]["events"] == 7
    if "sessions" in response.json:
        assert len(response.json["sessions"]) == 3
        assert sorted(s["score"] for s in response.json["sessions"]) == [1, 111, 111]


@pytest.mark.parametrize("event", ["page_view", "cta_click", "form_submit"])
def test_external_backend_records_correct_tenant(client, tenants, event):
    response = client.post("/api/website/events", headers={"X-Analytics-Key": tenants["key_a"]}, json={
        "site_id": tenants["a"].slug, "event": event,
        "page_url": "/external-page?private=value", "session_id": "external-visitor",
    })
    assert response.status_code == 201
    row = AnalyticsEvent.query.filter_by(user_session="external-visitor").one()
    assert row.structure_id == tenants["a"].id
    assert row.event_type == ("form_submitted" if event == "form_submit" else event)
    assert row.page_url == "/external-page"


@pytest.mark.parametrize("credential", ["key_a", "key_b"])
def test_authenticated_a_cannot_submit_for_b_even_with_b_credential(app, client, tenants, credential):
    login(client, app, tenants["users"]["admin"])
    count = AnalyticsEvent.query.count()
    response = client.post("/api/website/events", headers={"X-Analytics-Key": tenants[credential]}, json={
        "site_id": tenants["b"].slug, "event": "page_view", "page_url": "/forbidden",
    })
    assert response.status_code == 403
    assert AnalyticsEvent.query.count() == count


def test_backend_a_credential_cannot_be_used_with_b_tracking_id(client, tenants):
    response = client.post("/api/website/events", headers={"X-Analytics-Key": tenants["key_a"]}, json={
        "site_id": tenants["b"].slug, "event": "page_view", "page_url": "/forbidden",
    })
    assert response.status_code == 403


@pytest.mark.parametrize("site_id,key", [(None, "valid"), ("", "valid"), ("unknown", "valid"),
                                         ("valid", ""), ("valid", "tampered")])
def test_missing_or_invalid_identifier_or_key_rejected(client, tenants, site_id, key):
    response = client.post("/api/website/events", headers={
        "X-Analytics-Key": tenants["key_a"] if key == "valid" else key,
    }, json={"site_id": tenants["a"].slug if site_id == "valid" else site_id,
             "event": "page_view", "page_url": "/rejected"})
    assert response.status_code == 403
    assert AnalyticsEvent.query.filter_by(page_url="/rejected").count() == 0


@pytest.mark.parametrize("location", ["body", "props", "query", "header"])
def test_ingestion_parameters_cannot_override_site_tenant(client, tenants, location):
    payload = {"site_id": tenants["a"].slug, "event": "page_view", "page_url": "/override"}
    headers = {"X-Analytics-Key": tenants["key_a"]}
    query = {}
    if location == "body":
        payload["structure_id"] = tenants["b"].id
    elif location == "props":
        payload["props"] = {"organization_id": tenants["b"].id}
    elif location == "query":
        query["site_id"] = tenants["b"].slug
    else:
        headers["X-Structure-ID"] = str(tenants["b"].id)
    response = client.post("/api/website/events", json=payload, headers=headers, query_string=query)
    assert response.status_code == 403
    assert AnalyticsEvent.query.filter_by(page_url="/override").count() == 0


def test_ambient_tenant_and_session_role_cannot_override_database_actor(app, client, tenants):
    @app.before_request
    def injected_ambient_tenant():
        g.structure_id = tenants["b"].id

    login(client, app, tenants["users"]["admin"])
    with client.session_transaction() as sess:
        sess["role"] = "superadmin"
        sess["structure_id"] = tenants["b"].id
    response = client.get(READ_ENDPOINTS[0])
    assert response.status_code == 200
    assert response.json["scope"]["structure_id"] == tenants["a"].id
    assert response.json["summary"]["events"] == 3
    assert client.get(READ_ENDPOINTS[0], headers={"X-Structure-ID": str(tenants["b"].id)}).status_code == 403
    assert client.get(READ_ENDPOINTS[0], query_string=[
        ("structure_id", tenants["a"].id), ("structure_id", tenants["b"].id),
    ]).status_code == 403


def test_scoped_config_and_dashboard_context(app, client, tenants):
    login(client, app, tenants["users"]["admin"])
    config = client.get("/admin/api/website-tracking")
    assert config.status_code == 200
    assert config.json["site_id"] == tenants["a"].slug
    assert config.json["ingestion_key"] == tenants["key_a"]
    assert "no-store" in config.headers["Cache-Control"]
    html = client.get("/admin/conversion-dashboard").get_data(as_text=True)
    assert "Organization A / analytics-a / https://a.example" in html
    assert "Organization B" not in html


def test_global_dashboard_context_and_configuration_require_selection(app, client, tenants):
    login(client, app, tenants["users"]["global"])
    assert "All organizations / sites" in client.get("/admin/conversion-dashboard").get_data(as_text=True)
    assert client.get("/admin/api/website-tracking").status_code == 400
    config = client.get("/admin/api/website-tracking", query_string={"site_id": tenants["b"].slug})
    assert config.status_code == 200
    assert config.json["ingestion_key"] == tenants["key_b"]


@pytest.mark.parametrize("identity", ["anonymous", "unscoped", "inactive", "stale"])
def test_scope_fails_closed(app, client, tenants, session, identity):
    if identity == "unscoped":
        login(client, app, tenants["users"]["unscoped"])
    elif identity == "inactive":
        admin = tenants["users"]["admin"]
        admin.is_active = False
        session.commit()
        login(client, app, admin)
    elif identity == "stale":
        with client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_user_id"] = 999999
    assert client.get(READ_ENDPOINTS[0]).status_code == 403


def test_dispatch_scope_and_legacy_global_endpoints(app, client, tenants):
    login(client, app, tenants["users"]["admin"])
    response = client.post("/admin/api/revenue-alert-dispatch")
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["dispatched"][0]["structure_id"] == tenants["a"].id
    assert response.json["dispatched"][0]["session"] == "same-session"
    assert client.post("/admin/api/revenue-alert-dispatch", json={
        "organization_id": tenants["b"].id,
    }).status_code == 403
    for endpoint in ("/api/analytics/data", "/api/analytics/bookmarks", "/analytics/stream"):
        assert client.get(endpoint).status_code == 403


def test_legacy_events_cannot_bypass_external_credentials(client, tenants):
    count = AnalyticsEvent.query.count()
    response = client.post("/events", json={
        "site_id": tenants["b"].slug, "event": "page_view", "page_url": "/offre",
    })
    assert response.status_code == 403
    assert AnalyticsEvent.query.count() == count


def test_first_party_page_views_have_explicit_structure(client, tenants):
    response = client.get("/offre", headers={
        "User-Agent": "Mozilla/5.0", "X-Forwarded-For": "203.0.113.10",
    })
    assert response.status_code == 200
    default = Structure.query.filter_by(slug="default").one()
    assert AnalyticsEvent.query.filter_by(page_url="/offre").one().structure_id == default.id


def test_bearer_actor_is_scoped_and_cannot_select_foreign_site(app, client, tenants):
    from backend.helpchain_backend.src.jwt_utils import encode_access_token

    token = encode_access_token(tenants["users"]["admin"].id)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(READ_ENDPOINTS[0], headers=headers)
    assert response.status_code == 200
    assert response.json["summary"]["events"] == 3
    assert client.get(READ_ENDPOINTS[0], headers=headers, query_string={
        "site_id": tenants["b"].slug,
    }).status_code == 403


@pytest.mark.parametrize("payload", [[], {"event": "unknown", "page_url": "/"},
                                     {"event": "page_view", "page_url": "https://other.example"},
                                     {"event": "page_view", "page_url": "/", "session_id": 7}])
def test_malformed_external_events_are_rejected(client, tenants, payload):
    if isinstance(payload, dict):
        payload["site_id"] = tenants["a"].slug
    count = AnalyticsEvent.query.count()
    response = client.post("/api/website/events", json=payload, headers={"X-Analytics-Key": tenants["key_a"]})
    assert response.status_code == 400
    assert AnalyticsEvent.query.count() == count


def test_score_explanations_do_not_mix_same_session_between_tenants(app, client, tenants):
    from backend.helpchain_backend.src.models import ScoreExplanation

    login(client, app, tenants["users"]["global"])
    assert client.get("/admin/api/revenue-intelligence").status_code == 200
    rows = ScoreExplanation.query.filter_by(subject_type="website_analytics_session").all()
    assert len(rows) == 3
    assert len({row.subject_id for row in rows}) == 3
    assert sorted(row.total_score for row in rows) == [1, 111, 111]
