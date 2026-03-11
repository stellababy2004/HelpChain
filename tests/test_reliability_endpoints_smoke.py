from __future__ import annotations


def test_health_endpoint_reports_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.is_json

    data = resp.get_json() or {}
    assert "status" in data
    assert "app" in data
    assert "db" in data
    assert data["status"] == "ok"
    assert data["app"] == "ok"
    assert data["db"] == "ok"


def test_admin_sanity_requires_admin_session(client):
    resp = client.get("/admin/sanity", follow_redirects=False)
    # Protected admin surface: redirect to login or hide behind 404.
    assert resp.status_code in (302, 303, 404)


def test_admin_sanity_renders_for_authenticated_admin(authenticated_admin_client):
    resp = authenticated_admin_client.get("/admin/sanity")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert "Application" in html
    assert "Base de données" in html  # Database
    assert "File admin" in html  # Admin queue sanity
    assert "Sentry configuré" in html  # Error capture
