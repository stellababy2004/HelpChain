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


@pytest.fixture
def operator_client(app, db_session):
    client = app.test_client()
    admin = db_session.query(AdminUser).filter_by(email="ops@test.local").first()
    if not admin:
        admin = AdminUser(
            username="ops_user",
            email="ops@test.local",
            password_hash="x",
            role="ops",
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
    admin_id = admin.id
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["user_id"] = admin_id
        sess["admin_id"] = admin_id
        sess["admin_user_id"] = admin_id
        sess["role"] = "ops"
        sess["is_admin"] = True
        sess["admin_logged_in"] = True
        sess["is_authenticated"] = True
    return client


def test_operator_cannot_access_superadmin_pages(operator_client):
    for path in ("/admin/requests", "/admin/requests/new"):
        resp = operator_client.get(path, follow_redirects=False)
        assert resp.status_code in (403, 404)


def test_volunteer_cannot_access_admin_pages(authenticated_volunteer_client):
    resp = authenticated_volunteer_client.get("/admin/requests", follow_redirects=False)
    assert resp.status_code in (302, 403, 404)


def test_admin_invalid_request_id_returns_404(admin_login):
    resp = admin_login.get("/admin/requests/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_assign_nonexistent_social_request_returns_404(admin_login):
    resp = admin_login.post(
        "/requests/999999/assign",
        data={"assigned_to_user_id": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 404
