from datetime import datetime, timedelta, timezone


def test_admin_session_timeout_flash_and_redirect(authenticated_admin_client):
    client = authenticated_admin_client

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_last_seen"] = (
            datetime.now(timezone.utc) - timedelta(minutes=25)
        ).isoformat()

    resp = client.get("/admin/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Votre session a expiré. Veuillez vous reconnecter." in html


def test_sensitive_admin_route_requires_fresh_auth(authenticated_admin_client):
    client = authenticated_admin_client
    old = datetime.now(timezone.utc) - timedelta(minutes=20)

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_last_seen"] = datetime.now(timezone.utc).isoformat()
        sess["admin_auth_at"] = old.isoformat()

    resp = client.get("/admin/mfa/backup-codes", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/admin/re-auth" in (resp.headers.get("Location") or "")


def test_sensitive_admin_route_allows_recent_fresh_auth(authenticated_admin_client):
    client = authenticated_admin_client
    now = datetime.now(timezone.utc)

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_last_seen"] = now.isoformat()
        sess["admin_auth_at"] = now.isoformat()

    resp = client.get("/admin/mfa/backup-codes", follow_redirects=False)
    assert resp.status_code in (200, 302, 303)
    location = resp.headers.get("Location", "")
    assert "/admin/re-auth" not in location


def test_cookie_security_flags_are_hardened(app):
    assert app.config.get("SESSION_COOKIE_HTTPONLY") is True
    assert app.config.get("SESSION_COOKIE_SAMESITE") == "Lax"
    assert app.config.get("REMEMBER_COOKIE_HTTPONLY") is True
    assert app.config.get("REMEMBER_COOKIE_SAMESITE") == "Lax"
