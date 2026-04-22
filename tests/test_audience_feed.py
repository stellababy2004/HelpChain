from backend.models_with_analytics import AnalyticsEvent, UserBehavior


def test_tracked_public_page_creates_page_view(client):
    response = client.get("/offre")

    assert response.status_code == 200
    event = AnalyticsEvent.query.filter_by(page_url="/offre").one()
    assert event.event_type == "page_view"
    assert event.event_category == "audience"
    assert event.user_session

    behavior = UserBehavior.query.filter_by(session_id=event.user_session).one()
    assert behavior.entry_page == "/offre"
    assert behavior.pages_visited == 1


def test_static_assets_do_not_create_page_view(client):
    client.get("/static/css/pages/admin-ui.css")

    assert AnalyticsEvent.query.filter_by(event_type="page_view").count() == 0


def test_referrer_is_captured(client):
    client.get("/deploiement", headers={"Referer": "https://www.linkedin.com/company/helpchain"})

    event = AnalyticsEvent.query.filter_by(page_url="/deploiement").one()
    assert event.referrer == "https://www.linkedin.com/company/helpchain"


def test_high_intent_page_view_is_stored(client):
    client.get("/demander-acces")

    event = AnalyticsEvent.query.filter_by(page_url="/demander-acces").one()
    assert event.event_label == "high_intent"


def test_audience_map_reads_feed_metrics(authenticated_admin_client):
    authenticated_admin_client.get("/offre")
    authenticated_admin_client.get("/demander-acces")

    response = authenticated_admin_client.get("/admin/audience-map")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "/offre" in html
    assert "/demander-acces" in html
    assert "2 visite(s) sur des pages a forte intention" in html


def test_feed_failure_does_not_break_page_rendering(client, monkeypatch):
    from backend.helpchain_backend.src.services import audience_feed

    def fail_tracking():
        raise RuntimeError("tracking unavailable")

    monkeypatch.setattr(audience_feed, "track_audience_page_view", fail_tracking)

    response = client.get("/offre")

    assert response.status_code == 200
