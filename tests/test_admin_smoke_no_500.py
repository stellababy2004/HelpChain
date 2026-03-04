import pytest

pytestmark = pytest.mark.smoke_admin


@pytest.fixture
def admin_login(authenticated_admin_client):
    return authenticated_admin_client


def _dbg(resp):
    body = resp.get_data(as_text=True)
    return (
        f"status={resp.status_code} "
        f"ctype={resp.headers.get('Content-Type')} "
        f"body[:300]={body[:300]!r}"
    )


def test_admin_ops_login_public_never_500(client):
    r = client.get("/admin/ops/login")

    assert r.status_code != 500, _dbg(r)
    assert r.status_code == 200, _dbg(r)

    html = r.get_data(as_text=True).lower()
    assert "<html" in html and "</head>" in html
    assert ("admin" in html) or ("login" in html)
    assert "traceback" not in html


@pytest.mark.parametrize(
    "path",
    [
        "/admin/requests",
        "/admin/risk",
        "/admin/security",
        "/admin/audit",
        "/admin/sla",
    ],
)
def test_admin_endpoints_never_500(client, admin_login, path):
    r = admin_login.get(path)

    assert r.status_code != 500, _dbg(r)
    assert r.status_code in (200, 302, 401, 403), _dbg(r)

    if r.status_code == 200:
        html = r.get_data(as_text=True).lower()
        assert "<html" in html and "</head>" in html
        assert "traceback" not in html


def test_admin_requests_script_contract(admin_login):
    r = admin_login.get("/admin/requests")
    assert r.status_code != 500, _dbg(r)
    assert r.status_code in (200, 302, 401, 403), _dbg(r)

    if r.status_code == 200:
        html = r.get_data(as_text=True)
        assert 'src="/static/js/admin-requests.js"' in html
        assert 'src="/static/js/admin-folds.js"' in html
