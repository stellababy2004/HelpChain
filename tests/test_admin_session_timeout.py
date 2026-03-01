from datetime import datetime, timedelta, timezone


def test_admin_session_timeout_redirects_to_login(authenticated_admin_client):
    client = authenticated_admin_client

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_last_seen"] = (
            datetime.now(timezone.utc) - timedelta(minutes=21)
        ).isoformat()

    resp = client.get("/admin/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location", "")
    assert "/admin/login" in location


def test_admin_session_timeout_refreshes_last_seen(authenticated_admin_client):
    client = authenticated_admin_client
    old_seen = datetime.now(timezone.utc) - timedelta(minutes=5)

    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_last_seen"] = old_seen.isoformat()

    resp = client.get("/admin/dashboard", follow_redirects=False)
    assert resp.status_code in (200, 302, 303)
    if resp.status_code in (302, 303):
        location = resp.headers.get("Location", "")
        assert "/admin/ops/login" not in location

    with client.session_transaction() as sess:
        refreshed = sess.get("admin_last_seen")
        assert refreshed is not None
        refreshed_dt = datetime.fromisoformat(refreshed)
        assert refreshed_dt > old_seen
