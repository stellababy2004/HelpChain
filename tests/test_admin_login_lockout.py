from backend.models import AdminLoginAttempt, AdminUser


def _ensure_admin_user(session, username: str, password: str) -> None:
    admin = session.query(AdminUser).filter_by(username=username).first()
    if not admin:
        admin = AdminUser(
            username=username,
            email=f"{username}@test.local",
            role="admin",
            is_active=True,
        )
        session.add(admin)
    admin.set_password(password)
    session.commit()


def test_admin_login_legacy_lockout_returns_429(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    username = "lockout_admin_legacy"
    _ensure_admin_user(session, username, "CorrectPass123")

    session.query(AdminLoginAttempt).delete()
    session.commit()

    for _ in range(5):
        resp = client.post(
            "/admin/login",
            data={"username": username, "password": "wrong-password"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

    blocked = client.post(
        "/admin/login",
        data={"username": username, "password": "wrong-password"},
        follow_redirects=False,
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_admin_ops_login_lockout_returns_429(client, session):
    username = "lockout_admin_ops"
    _ensure_admin_user(session, username, "CorrectPass123")

    session.query(AdminLoginAttempt).delete()
    session.commit()

    for _ in range(5):
        resp = client.post(
            "/admin/ops/login",
            data={"username": username, "password": "wrong-password"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

    blocked = client.post(
        "/admin/ops/login",
        data={"username": username, "password": "wrong-password"},
        follow_redirects=False,
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")

