from bs4 import BeautifulSoup

from backend.models_with_analytics import AnalyticsEvent


PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Forwarded-For": "203.0.113.42",
}


def test_public_pricing_page_renders_expected_offer_content(client):
    response = client.get("/tarifs", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Une coordination plus simple. Un tarif adapté à votre organisation." in html
    assert "HelpChain centralise les demandes, les affectations, le suivi" in html
    assert "À partir de 300 € / mois" in html
    assert "STRUCTURE" in html
    assert "À partir de 300 €/mois" in html
    assert "COORDINATION AVANCÉE" in html
    assert "À partir de 500 €/mois" in html
    assert "RÉSEAU / MULTI-STRUCTURES" in html
    assert "Sur devis" in html
    assert "Pilote de 30 jours — à partir de 250 €" in html


def test_public_pricing_pilot_cta_points_to_demo_and_uses_cta_event(client):
    response = client.get("/tarifs", headers=PUBLIC_HEADERS)
    soup = BeautifulSoup(response.get_data(as_text=True), "html.parser")

    cta = soup.select_one('a[href="/demo"][data-hc-event="cta_pricing_pilot"]')

    assert cta is not None
    assert cta["data-hc-event"].startswith("cta_")
    assert cta.get("data-hc-cta") == "pricing_pilot"
    assert "Demander un pilote" in cta.get_text(" ", strip=True)


def test_public_navigation_contains_pricing_link(client):
    response = client.get("/", headers=PUBLIC_HEADERS)
    soup = BeautifulSoup(response.get_data(as_text=True), "html.parser")

    nav_links = [
        link
        for link in soup.select('[data-hc-public-nav] a[href="/tarifs"], #hcMobileNav a[href="/tarifs"]')
        if "Tarifs" in link.get_text(" ", strip=True)
    ]
    nav_links.extend(
        link
        for link in soup.select('.hc-home-premium__nav a[href="/tarifs"]')
        if "Tarifs" in link.get_text(" ", strip=True)
    )

    assert nav_links


def test_public_pricing_page_view_is_tracked_with_existing_mechanism(client):
    response = client.get("/tarifs", headers=PUBLIC_HEADERS)

    assert response.status_code == 200
    event = AnalyticsEvent.query.filter_by(page_url="/tarifs", event_type="page_view").one()
    assert event.event_category == "audience"
    assert event.event_action == "page_view"
    assert event.event_label == "high_intent"


def test_public_pricing_cta_event_is_accepted_by_existing_events_endpoint(client):
    response = client.post(
        "/events",
        json={
            "event": "cta_pricing_pilot",
            "props": {
                "url": "/tarifs",
                "page": "/tarifs",
                "category": "conversion",
                "action": "click",
                "label": "Demander un pilote",
                "href": "/demo",
                "cta": "pricing_pilot",
                "intent": "pilot",
            },
        },
        headers=PUBLIC_HEADERS,
    )

    assert response.status_code == 201
    assert response.get_json() == {"ok": True}
    event = AnalyticsEvent.query.filter_by(event_type="cta_pricing_pilot").one()
    assert event.page_url == "/tarifs"
    assert event.event_category == "conversion"
    assert event.event_action == "click"
