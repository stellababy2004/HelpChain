import json
from pathlib import Path

from bs4 import BeautifulSoup

from backend.models_with_analytics import AnalyticsEvent, UserBehavior

PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Forwarded-For": "203.0.113.10",
}


def _audience_payload(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    payload = soup.select_one("#audienceMapPayload")
    assert payload is not None
    return json.loads(payload.get_text())


def test_tracked_public_page_creates_page_view(client):
    response = client.get("/offre", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    event = AnalyticsEvent.query.filter_by(page_url="/offre").one()
    assert event.event_type == "page_view"
    assert event.event_category == "audience"
    assert event.user_session

    behavior = UserBehavior.query.filter_by(session_id=event.user_session).one()
    assert behavior.entry_page == "/offre"
    assert behavior.pages_visited == 1
    assert behavior.ip_address is None
    assert behavior.user_agent is None
    assert event.user_ip is None
    assert event.user_agent is None



def test_public_page_captures_first_touch_utm(client):
    response = client.get(
        "/offre?utm_source=linkedin&utm_medium=social&utm_campaign=escp_octobre",
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 200

    behavior = UserBehavior.query.one()
    assert behavior.utm_source == "linkedin"
    assert behavior.utm_medium == "social"
    assert behavior.utm_campaign == "escp_octobre"

    event = AnalyticsEvent.query.filter_by(event_type="page_view").one()
    assert event.page_url == "/offre"
    assert "utm_" not in event.page_url


def test_public_page_keeps_first_touch_utm(client):
    first = client.get(
        "/offre?utm_source=linkedin&utm_medium=social&utm_campaign=escp_octobre",
        headers=PUBLIC_HEADERS,
    )
    second = client.get(
        "/demander-acces?utm_source=google&utm_medium=cpc&utm_campaign=other_campaign",
        headers=PUBLIC_HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    behavior = UserBehavior.query.one()
    assert behavior.pages_visited == 2
    assert behavior.utm_source == "linkedin"
    assert behavior.utm_medium == "social"
    assert behavior.utm_campaign == "escp_octobre"


def test_public_page_sanitizes_and_bounds_utm(client):
    campaign = "campaign!" + ("x" * 200)

    response = client.get(
        "/offre",
        query_string={
            "utm_source": " Linked In<script> ",
            "utm_medium": "paid social / test",
            "utm_campaign": campaign,
            "email": "private@example.com",
            "token": "super-secret",
        },
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 200

    behavior = UserBehavior.query.one()

    assert behavior.utm_source == "LinkedInscript"
    assert behavior.utm_medium == "paidsocialtest"
    assert behavior.utm_campaign == "campaign" + ("x" * 142)
    assert len(behavior.utm_source) <= 100
    assert len(behavior.utm_medium) <= 100
    assert len(behavior.utm_campaign) == 150

    event = AnalyticsEvent.query.filter_by(event_type="page_view").one()
    assert event.page_url == "/offre"
    assert "private@example.com" not in event.page_url
    assert "super-secret" not in event.page_url


def test_static_assets_do_not_create_page_view(client):
    client.get("/static/css/pages/admin-ui.css", headers=PUBLIC_HEADERS)

    assert AnalyticsEvent.query.filter_by(event_type="page_view").count() == 0


def test_referrer_is_captured(client):
    client.get(
        "/deploiement",
        headers={
            **PUBLIC_HEADERS,
            "Referer": "https://www.linkedin.com/company/helpchain",
        },
    )

    event = AnalyticsEvent.query.filter_by(page_url="/deploiement").one()
    assert event.referrer == "https://www.linkedin.com"


def test_referrer_sensitive_path_and_query_are_not_saved(client):
    client.get("/offre", headers={**PUBLIC_HEADERS, "Referer": "https://example.org/private?token=secret#fragment"})
    event = AnalyticsEvent.query.filter_by(page_url="/offre").one()
    assert event.referrer == "https://example.org"


def test_high_intent_page_view_is_stored(client):
    client.get("/demander-acces", headers=PUBLIC_HEADERS)

    event = AnalyticsEvent.query.filter_by(page_url="/demander-acces").one()
    assert event.event_label == "high_intent"


def test_audience_map_reads_feed_metrics(app, client):
    from backend.helpchain_backend.src.routes.admin import _build_audience_map_context

    client.get("/offre", headers=PUBLIC_HEADERS)
    client.get("/demander-acces", headers=PUBLIC_HEADERS)
    behavior = UserBehavior.query.one()
    behavior.location = "Boulogne-Billancourt, France"
    
    from backend.extensions import db
    db.session.commit()

    with app.app_context():
        payload = _build_audience_map_context()
    pages = {row["label"]: int(row["count"]) for row in payload["page_rows"]}
    revenue_rows = payload["revenue_radar_rows"]

    assert "Offre" in pages
    assert any("demander" in label.lower() for label in pages)
    assert pages["Offre"] >= 1
    assert any(count >= 1 for label, count in pages.items() if "demander" in label.lower())
    assert any(int(row["pages_count"]) >= 2 for row in revenue_rows)
    assert payload["territory_summaries"]
    assert payload["territory_summaries"][0]["territory"] == "Boulogne-Billancourt"
    assert any(row["territory"] == "Boulogne-Billancourt" for row in revenue_rows)


def test_feed_failure_does_not_break_page_rendering(client, monkeypatch):
    from backend.helpchain_backend.src.services import audience_feed

    def fail_tracking():
        raise RuntimeError("tracking unavailable")

    monkeypatch.setattr(audience_feed, "track_audience_page_view", fail_tracking)

    response = client.get("/offre", headers=PUBLIC_HEADERS)

    assert response.status_code == 200


def test_events_public_commercial_page_is_persisted(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/offre", "category": "audience"}},
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 201
    assert response.get_json() == {"ok": True}
    event = AnalyticsEvent.query.one()
    assert event.page_url == "/offre"
    assert event.event_type == "page_view"
    assert event.user_ip is None
    assert event.user_agent is None
    assert event.screen_resolution is None


def test_events_admin_path_is_ignored(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/admin/revenue", "category": "audience"}},
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0
    assert UserBehavior.query.count() == 0


def test_events_static_asset_is_ignored(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/static/app.js", "category": "audience"}},
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0


def test_events_bot_user_agent_is_ignored(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/offre", "category": "audience"}},
        headers={
            "User-Agent": "Mozilla/5.0 compatible; Googlebot/2.1",
            "X-Forwarded-For": "203.0.113.15",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0


def test_events_local_traffic_is_ignored_when_marker_present(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/offre", "category": "audience"}},
        headers={
            "User-Agent": PUBLIC_HEADERS["User-Agent"],
            "X-Forwarded-For": "127.0.0.1",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0


def test_events_founder_marker_is_ignored(client):
    response = client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/offre", "category": "audience"}},
        headers={
            "User-Agent": PUBLIC_HEADERS["User-Agent"],
            "X-Forwarded-For": "176.187.42.10",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0


def test_events_admin_session_is_ignored(authenticated_admin_client):
    response = authenticated_admin_client.post(
        "/events",
        json={"event": "page_view", "props": {"url": "/offre", "category": "audience"}},
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ignored": True}
    assert AnalyticsEvent.query.count() == 0


def test_admin_page_requests_do_not_pollute_audience_feed(authenticated_admin_client):
    response = authenticated_admin_client.get("/offre", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    assert AnalyticsEvent.query.count() == 0
    assert UserBehavior.query.count() == 0


def test_events_public_cta_click_is_persisted(client):
    response = client.post(
        "/events",
        json={
            "event": "revenue_cta_click",
            "props": {
                "page": "/",
                "cta": "hero_pilot_access",
                "intent": "pilot",
            },
        },
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 201
    assert response.get_json() == {"ok": True}
    event = AnalyticsEvent.query.one()
    assert event.page_url == "/"
    assert event.event_type == "revenue_cta_click"


def test_homepage_pilot_cta_preserves_custom_event_and_counts_once(
    client,
    authenticated_admin_client,
):
    response = client.get("/", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    soup = BeautifulSoup(response.get_data(as_text=True), "html.parser")
    cta = soup.select_one('a[href="/demo"][data-hc-event="home_primary_cta"]')
    assert cta is not None
    assert "Demander" in cta.get_text(" ", strip=True)

    script = Path("static/js/hc-core.js").read_text(encoding="utf-8")
    assert 'type = "cta_demo_click";' in script
    assert "handled by hc-intent-tracking.js" not in script

    for event_name in ("home_primary_cta", "cta_demo_click"):
        event_response = client.post(
            "/events",
            json={
                "event": event_name,
                "props": {
                    "page": "/",
                    "url": "/",
                    "category": "conversion",
                    "action": "click",
                    "label": "Demander un pilote",
                    "href": "/demo",
                },
            },
            headers=PUBLIC_HEADERS,
        )
        assert event_response.status_code == 201

    funnel = authenticated_admin_client.get("/admin/api/conversion-funnel?days=30")

    assert funnel.status_code == 200
    payload = funnel.get_json()
    assert payload["summary"]["cta_clicks"] == 1
    assert payload["summary"]["page_views"] == 1
    assert AnalyticsEvent.query.filter_by(event_type="home_primary_cta").count() == 1
    assert AnalyticsEvent.query.filter_by(event_type="cta_demo_click").count() == 1
    assert payload["top_ctas"] == [{"event": "cta_demo_click", "count": 1}]
