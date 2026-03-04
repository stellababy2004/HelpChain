import pytest

pytestmark = pytest.mark.smoke_admin


@pytest.fixture
def admin_login(authenticated_admin_client):
    return authenticated_admin_client


@pytest.mark.parametrize(
    "path",
    [
        "/admin/api/risk-kpis",
        "/admin/api/ops-kpis",
        "/admin/api/dashboard",
    ],
)
def test_admin_api_never_500(admin_login, path):
    r = admin_login.get(path)
    assert r.status_code != 500

    assert r.status_code in (200, 302, 401, 403)

    if r.status_code == 200:
        ctype = (r.headers.get("Content-Type") or "").lower()
        assert "application/json" in ctype
        data = r.get_json()
        assert isinstance(data, dict)

        if path == "/admin/api/risk-kpis":
            assert "generated_at" in data
            assert "stale_count" in data
        elif path == "/admin/api/ops-kpis":
            assert "window_days" in data
            assert "health" in data
        elif path == "/admin/api/dashboard":
            assert "total_requests" in data
            assert "counts_by_status" in data
