from datetime import timedelta
import os

from backend.models import AdminLoginAttempt, AdminUser, utc_now


GENERIC_FAIL_MSG = "Identifiants invalides ou accès temporairement bloqué."
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "test-password")


def _ensure_admin_user(session, username: str, password: str) -> AdminUser:
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
    return admin


def test_admin_login_lockout_uses_generic_message(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    username = "lockout_generic_admin"
    ip = "203.0.113.10"
    now = utc_now()

    _ensure_admin_user(session, username, TEST_ADMIN_PASSWORD)
    session.query(AdminLoginAttempt).delete()
    session.add_all(
        [
            AdminLoginAttempt(
                created_at=now - timedelta(minutes=1),
                username=username,
                ip=ip,
                success=False,
            )
            for _ in range(5)
        ]
    )
    session.commit()

    blocked = client.post(
        "/admin/login",
        data={"username": username, "password": "wrong-password"},
        environ_base={"REMOTE_ADDR": ip},
        follow_redirects=False,
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")
    html = blocked.get_data(as_text=True)
    assert GENERIC_FAIL_MSG in html


def test_admin_login_success_clears_recent_failed_bucket(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    username = "clear_bucket_admin"
    password = TEST_ADMIN_PASSWORD
    ip = "203.0.113.11"
    now = utc_now()

    _ensure_admin_user(session, username, password)
    session.query(AdminLoginAttempt).delete()
    session.add_all(
        [
            AdminLoginAttempt(
                created_at=now - timedelta(minutes=2),
                username=username,
                ip=ip,
                success=False,
            )
            for _ in range(4)
        ]
    )
    session.commit()

    ok = client.post(
        "/admin/login",
        data={"username": username, "password": password},
        environ_base={"REMOTE_ADDR": ip},
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)

    remaining_recent_fails = (
        session.query(AdminLoginAttempt)
        .filter(
            AdminLoginAttempt.username == username,
            AdminLoginAttempt.ip == ip,
            AdminLoginAttempt.success.is_(False),
            AdminLoginAttempt.created_at >= (now - timedelta(minutes=5)),
        )
        .count()
    )
    assert remaining_recent_fails == 0
