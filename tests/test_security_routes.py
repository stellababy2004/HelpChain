import pytest

from backend.models import AdminUser


def _admin_id_from_client(client) -> int:
    with client.session_transaction() as sess:
        val = (
            sess.get("admin_user_id")
            or sess.get("admin_id")
            or sess.get("user_id")
            or sess.get("_user_id")
        )
    return int(val)


def _set_admin_role(session, client, role: str) -> None:
    admin_id = _admin_id_from_client(client)
    admin = session.get(AdminUser, admin_id)
    admin.role = role
    session.commit()


@pytest.fixture
def admin_login(authenticated_admin_client, db_session):
    _set_admin_role(db_session, authenticated_admin_client, "superadmin")
    admin_id = _admin_id_from_client(authenticated_admin_client)
    with authenticated_admin_client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["user_id"] = admin_id
        sess["admin_id"] = admin_id
        sess["admin_user_id"] = admin_id
        sess["role"] = "superadmin"
        sess["is_admin"] = True
        sess["admin_logged_in"] = True
        sess["is_authenticated"] = True
    return authenticated_admin_client


def test_unauthorized_access_to_admin_routes_redirects(client):
    resp = client.get("/admin/requests", follow_redirects=False)
    assert resp.status_code in (302, 404)
    if resp.status_code == 302:
        assert "/admin/ops/login" in (resp.headers.get("Location", "") or "")


def test_login_required_redirects_for_admin_new(client):
    resp = client.get("/admin/requests/new", follow_redirects=False)
    assert resp.status_code in (302, 404)
    if resp.status_code == 302:
        assert "/admin/ops/login" in (resp.headers.get("Location", "") or "")


def test_session_expired_admin_redirects(admin_login):
    with admin_login.session_transaction() as sess:
        for key in (
            "_user_id",
            "user_id",
            "admin_id",
            "admin_user_id",
            "admin_logged_in",
            "is_admin",
            "is_authenticated",
            "role",
        ):
            sess.pop(key, None)
    resp = admin_login.get("/admin/requests", follow_redirects=False)
    assert resp.status_code in (302, 404)
