import time

CRITICAL_PUBLIC_HTML_ROUTES = [
    "/",
    "/professionnels",
    "/gouvernance",
    "/orienter",
    "/admin/ops/login",
]

CRITICAL_ADMIN_HTML_ROUTES = [
    "/admin/requests",
]

CRITICAL_PUBLIC_JSON_ROUTES = [
    "/api/ai/status",
]

CRITICAL_ADMIN_JSON_ROUTES = [
    "/admin/api/dashboard",
    "/admin/api/risk-kpis",
]


def _dbg(resp, path: str) -> str:
    body = resp.get_data(as_text=True)
    return (
        f"path={path} status={resp.status_code} "
        f"ctype={resp.headers.get('Content-Type')} body[:300]={body[:300]!r}"
    )


def _assert_html_integrity(resp, path: str) -> None:
    assert resp.status_code != 500, f"HTML route crashed: {path} | {_dbg(resp, path)}"
    assert resp.status_code in (200, 302, 303, 401, 403), _dbg(resp, path)
    if resp.status_code == 200:
        html = resp.get_data(as_text=True).lower()
        headers = resp.headers
        assert "Content-Security-Policy" in headers
        assert "X-Content-Type-Options" in headers
        assert "<html" in html
        assert "</head>" in html
        assert "traceback" not in html
        assert "werkzeug debugger" not in html


def _assert_json_integrity(resp, path: str) -> None:
    assert resp.status_code != 500, f"API route crashed: {path} | {_dbg(resp, path)}"
    assert resp.status_code in (200, 302, 303, 401, 403), _dbg(resp, path)
    if resp.status_code == 200:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        assert "application/json" in ctype


def test_public_html_routes_never_500(client):
    for path in CRITICAL_PUBLIC_HTML_ROUTES:
        start = time.time()
        resp = client.get(path)
        elapsed = time.time() - start
        assert elapsed < 2.5, f"Slow endpoint: {path} took {elapsed:.2f}s"
        _assert_html_integrity(resp, path)


def test_admin_html_routes_never_500(authenticated_admin_client):
    for path in CRITICAL_ADMIN_HTML_ROUTES:
        start = time.time()
        resp = authenticated_admin_client.get(path)
        elapsed = time.time() - start
        assert elapsed < 2.5, f"Slow endpoint: {path} took {elapsed:.2f}s"
        _assert_html_integrity(resp, path)


def test_public_json_routes_never_500(client):
    for path in CRITICAL_PUBLIC_JSON_ROUTES:
        start = time.time()
        resp = client.get(path)
        elapsed = time.time() - start
        assert elapsed < 2.5, f"Slow endpoint: {path} took {elapsed:.2f}s"
        _assert_json_integrity(resp, path)
        if path == "/api/ai/status" and resp.status_code == 200:
            data = resp.get_json()
            assert isinstance(data, dict)
            assert "status" in data
            assert data["status"] in ("ok", "ready", "healthy")
            assert (
                ("version" in data)
                or ("git_sha" in data)
                or ("active_provider" in data)
                or ("providers" in data)
            )


def test_admin_json_routes_never_500(authenticated_admin_client):
    for path in CRITICAL_ADMIN_JSON_ROUTES:
        start = time.time()
        resp = authenticated_admin_client.get(path)
        elapsed = time.time() - start
        assert elapsed < 2.5, f"Slow endpoint: {path} took {elapsed:.2f}s"
        _assert_json_integrity(resp, path)
