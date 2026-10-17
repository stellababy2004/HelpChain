import os
from unittest.mock import patch

from backend.helpchain_backend.src.app import create_app


def test_hsts_is_set_for_production_https():
    with patch.dict(os.environ, {"FLASK_CONFIG": "production"}, clear=False):
        app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        })

        with app.test_client() as client:
            response = client.get(
                "/",
                environ_overrides={"wsgi.url_scheme": "https"},
            )

    assert response.headers.get("Strict-Transport-Security") == (
        "max-age=31536000; includeSubDomains"
    )


def test_hsts_is_not_set_over_http():
    with patch.dict(os.environ, {"FLASK_CONFIG": "production"}, clear=False):
        app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        })

        with app.test_client() as client:
            response = client.get(
                "/",
                environ_overrides={"wsgi.url_scheme": "http"},
            )

    assert response.headers.get("Strict-Transport-Security") is None
