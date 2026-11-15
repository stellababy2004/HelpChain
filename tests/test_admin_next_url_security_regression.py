import pytest

from backend.helpchain_backend.src.routes.admin import _safe_next_url


@pytest.mark.parametrize(
    "candidate",
    [
        "https://evil.com/admin",
        "//evil.com/admin",
        r"/admin\evil.com",
        "/administrator",
        "/public",
        "javascript:alert(1)",
        "https:%2f%2fevil.com",
    ],
)
def test_unsafe_admin_next_urls_are_rejected(app, candidate):
    with app.test_request_context("/admin/login"):
        assert _safe_next_url(candidate) == ""


@pytest.mark.parametrize(
    "candidate",
    ["/admin", "/admin/dashboard", "/ops", "/ops/workspace"],
)
def test_valid_internal_next_urls_are_allowed(app, candidate):
    with app.test_request_context("/admin/login"):
        assert _safe_next_url(candidate) == candidate


from types import SimpleNamespace

from backend.helpchain_backend.src.routes.admin import (
    _next_url_for_admin_user,
)


@pytest.mark.parametrize(
    "role, expected",
    [
        ("admin", "/ops/workspace"),
        ("ops", "/ops/workspace"),
        ("readonly", "/ops/workspace"),
        ("superadmin", "/ops/workspace"),
        ("unknown", ""),
    ],
)
def test_ops_next_url_respects_admin_role(app, role, expected):
    user = SimpleNamespace(role=role, structure_id=1)

    with app.test_request_context("/admin/login"):
        assert _next_url_for_admin_user(user, "/ops/workspace") == expected


def test_admin_next_url_rejects_missing_user(app):
    with app.test_request_context("/admin/login"):
        assert _next_url_for_admin_user(None, "/admin/dashboard") == ""


@pytest.mark.parametrize(
    "candidate",
    [
        "https://evil.com/admin",
        "//evil.com/admin",
        "/public",
    ],
)
def test_redirect_helper_never_redirects_to_unsafe_next(app, candidate):
    from backend.helpchain_backend.src.routes.admin import (
        _redirect_to_safe_next,
    )

    with app.test_request_context("/admin/login"):
        response = _redirect_to_safe_next(candidate, "/admin/login")

        assert response.status_code == 303
        assert response.headers["Location"] == "/admin/login"
