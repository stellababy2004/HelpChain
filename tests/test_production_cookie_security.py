import os
from unittest.mock import patch

from backend.helpchain_backend.src.app import create_app


def test_production_session_cookie_remains_secure():
    with patch.dict(os.environ, {"FLASK_CONFIG": "production"}, clear=False):
        app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        })

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
