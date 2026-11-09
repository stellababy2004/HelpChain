import pytest
from flask import Flask
from unittest.mock import patch

from backend.helpchain_backend.src.app import _validate_production_security_config


def _app(*, secret_key="s" * 40, debug=False):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secret_key, DEBUG=debug)
    app.debug = debug
    return app


@pytest.mark.parametrize("secret", [None, "", "dev-only-change-me", "test", "short"])
def test_production_rejects_missing_development_or_short_secret(secret):
    app = _app(secret_key=secret)
    with pytest.raises(RuntimeError, match="SECRET_KEY is missing or invalid"):
        _validate_production_security_config(app, "production")


def test_production_rejects_debug():
    app = _app(debug=True)
    with pytest.raises(RuntimeError, match="DEBUG must be disabled"):
        _validate_production_security_config(app, "production")


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_production_rejects_flask_debug_enabled(value):
    app = _app()
    with patch.dict("os.environ", {"FLASK_DEBUG": value}, clear=False):
        with pytest.raises(RuntimeError, match="DEBUG must be disabled"):
            _validate_production_security_config(app, "production")


def test_production_accepts_flask_debug_false():
    app = _app()
    with patch.dict("os.environ", {"FLASK_DEBUG": "false"}, clear=False):
        _validate_production_security_config(app, "production")


def test_production_accepts_valid_secret_without_exposing_it():
    app = _app()
    _validate_production_security_config(app, "production")


@pytest.mark.parametrize("env_name", ["", "development", "testing"])
def test_non_production_modes_remain_available(env_name):
    app = _app(secret_key="short", debug=True)
    _validate_production_security_config(app, env_name)
