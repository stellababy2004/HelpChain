from bs4 import BeautifulSoup

from backend.appy import app


PUBLIC_ROUTES = [
    "/",
    "/about",
    "/gouvernance",
    "/comment_ca_marche",
    "/collectivites_associations",
    "/cas_usage",
    "/deploiement",
    "/simulation-operationnelle",
    "/offre",
    "/tarifs",
    "/pilotage_indicateurs",
    "/partenariats",
    "/pourquoi_helpchain",
    "/vision_europeenne",
    "/securite",
    "/architecture",
    "/pour-les-structures",
    "/professionnels",
    "/faq",
    "/contact",
    "/confidentialite",
    "/conditions_utilisation",
    "/legal",
    "/success_stories",
]


KNOWN_FRENCH_FALLBACKS = (
    "Gouvernance de la plateforme",
    "Architecture de la plateforme",
    "Une situation ne disparaît plus dans le silence opérationnel",
    "Professionnels | Plateforme de coordination opérationnelle HelpChain",
    "Déployez une plateforme de coordination opérationnelle sans désorganiser vos équipes.",
)


def test_public_routes_render_in_all_supported_public_locales():
    for locale in ("fr", "bg", "en"):
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["lang"] = locale
            for route in PUBLIC_ROUTES:
                response = client.get(route)
                assert response.status_code == 200, (locale, route)
                assert response.headers["Content-Language"] == locale
                soup = BeautifulSoup(response.data, "html.parser")
                assert soup.title and soup.title.get_text(strip=True)
                assert soup.find("h1") and soup.find("h1").get_text(strip=True)
                assert soup.find("nav") is not None


def test_known_french_fallback_headings_are_absent_from_bg_and_en():
    for locale in ("bg", "en"):
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["lang"] = locale
            for route in PUBLIC_ROUTES:
                soup = BeautifulSoup(client.get(route).data, "html.parser")
                heading = soup.find("h1").get_text(" ", strip=True)
                assert heading not in KNOWN_FRENCH_FALLBACKS, (locale, route, heading)


def test_locale_policy_defaults_to_french_and_persists_selected_language(app):
    with app.test_client() as client:
        response = client.get("/tarifs", headers={"Accept-Language": "bg, en;q=0.9, ru;q=0.8"})
        assert response.status_code == 200
        assert response.headers["Content-Language"] == "fr"

        switched = client.get("/set-lang/bg", follow_redirects=False)
        assert switched.status_code in (301, 302, 303, 307, 308)
        assert client.get("/tarifs").headers["Content-Language"] == "bg"

        switched = client.get("/set-lang/en", follow_redirects=False)
        assert switched.status_code in (301, 302, 303, 307, 308)
        assert client.get("/tarifs").headers["Content-Language"] == "en"

        assert client.get("/set-lang/ru").status_code == 404
        assert client.get("/set-lang/de").status_code == 404


def test_public_architecture_and_deployment_have_utf8_localized_content(app):
    with app.test_client() as client:
        with client.session_transaction() as browser_session:
            browser_session["lang"] = "bg"

        architecture = client.get("/architecture")
        deployment = client.get("/deploiement")
        assert architecture.status_code == 200
        assert deployment.status_code == 200
        architecture_html = architecture.data.decode("utf-8")
        deployment_html = deployment.data.decode("utf-8")
        for text in (
            "ПОТРЕБИТЕЛИ И ЕКИПИ",
            "КООРДИНАЦИЯ ЧРЕЗ HELPCHAIN",
            "Управление и достъп",
            "Сигурност и проследимост",
            "Непрекъснатост и развитие",
        ):
            assert text in architecture_html
        assert "?????" not in deployment_html
        assert "�" not in deployment_html
