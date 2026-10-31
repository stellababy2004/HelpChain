import pytest
from flask import Flask
from backend.helpchain_backend.src.security.api_authz import require_roles

from backend.helpchain_backend.src.app import _validate_production_secret_config


def _app(secret_key: str, jwt_secret_key: str) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key,
        JWT_SECRET_KEY=jwt_secret_key,
        TESTING=False,
    )
    return app


def test_production_secret_validation_accepts_long_non_placeholder_keys():
    app = _app("s" * 64, "j" * 64)

    _validate_production_secret_config(app, "production")


@pytest.mark.parametrize(
    "secret_key,jwt_secret_key",
    [
        ("", "j" * 64),
        ("s" * 64, ""),
        ("dev-only-change-me", "j" * 64),
        ("s" * 64, "dev-secret-change-me"),
        ("s" * 31, "j" * 64),
    ],
)
def test_production_secret_validation_rejects_missing_or_unsafe_keys(
    secret_key: str, jwt_secret_key: str
):
    app = _app(secret_key, jwt_secret_key)

    with pytest.raises(RuntimeError, match="Production startup refused"):
        _validate_production_secret_config(app, "production")


def test_production_secret_validation_rejects_placeholder_variants():
    app = _app("replace-with-a-long-random-secret", "replace-with-a-long-random-secret")

    with pytest.raises(RuntimeError, match="Production startup refused"):
        _validate_production_secret_config(app, "production")


def test_production_signal_is_enforced_for_render(monkeypatch):
    app = _app("dev-only-change-me", "dev-only-change-me")
    monkeypatch.setenv("RENDER", "true")

    with pytest.raises(RuntimeError, match="Production startup refused"):
        _validate_production_secret_config(app, "")


def test_non_production_secret_validation_preserves_local_development():
    app = _app("dev-only-change-me", "dev-secret-change-me")

    _validate_production_secret_config(app, "development")


def test_api_role_guard_rejects_other_admin_roles(monkeypatch):
    app = Flask(__name__)

    @require_roles("admin")
    def protected():
        return "ok"

    monkeypatch.setattr(
        "backend.helpchain_backend.src.security.api_authz.resolve_bearer_admin_actor",
        lambda: type("Actor", (), {"role": "ops", "is_admin": True})(),
    )
    with app.test_request_context("/"):
        response = protected()

    assert response[1] == 403


def test_api_role_guard_allows_admin_and_superadmin(monkeypatch):
    app = Flask(__name__)

    @require_roles("admin")
    def protected():
        return "ok"

    for role in ("admin", "superadmin"):
        monkeypatch.setattr(
            "backend.helpchain_backend.src.security.api_authz.resolve_bearer_admin_actor",
            lambda role=role: type("Actor", (), {"role": role, "is_admin": True})(),
        )
        with app.test_request_context("/"):
            assert protected() == "ok"


def test_session_csrf_guard_skips_bearer_requests(monkeypatch):
    from backend.helpchain_backend.src.routes import api as api_routes

    app = Flask(__name__)
    app.config["WTF_CSRF_ENABLED"] = True
    protected_calls = []
    monkeypatch.setattr(
        api_routes.csrf,
        "protect",
        lambda: protected_calls.append(True),
    )

    with app.test_request_context(
        "/", headers={"Authorization": "Bearer test-token"}
    ):
        api_routes._protect_session_mutation()
    assert protected_calls == []


def test_session_csrf_guard_protects_cookie_requests(monkeypatch):
    from backend.helpchain_backend.src.routes import api as api_routes

    app = Flask(__name__)
    app.config["WTF_CSRF_ENABLED"] = True
    protected_calls = []
    monkeypatch.setattr(
        api_routes.csrf,
        "protect",
        lambda: protected_calls.append(True),
    )

    with app.test_request_context("/"):
        api_routes._protect_session_mutation()
    assert protected_calls == [True]
