from datetime import timedelta
import os

from werkzeug.middleware.proxy_fix import ProxyFix

from backend.models import AdminLoginAttempt, AdminUser, utc_now

GENERIC_FAIL_MSG = "Identifiants invalides ou accès temporairement bloqué."
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "TestPassword1")


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


def test_admin_login_rate_limit_per_ip(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    username = "rate_limit_admin"
    ip = "203.0.113.12"

    _ensure_admin_user(session, username, TEST_ADMIN_PASSWORD)
    session.query(AdminLoginAttempt).delete()
    session.commit()

    responses = []
    for _ in range(6):
        responses.append(
            client.post(
                "/admin/login",
                data={"username": username, "password": "wrong-password"},
                environ_base={"REMOTE_ADDR": ip},
                follow_redirects=False,
            )
        )

    assert responses[-1].status_code == 429
    retry_after = responses[-1].headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) > 0


def test_spoofed_xff_cannot_bypass_admin_login_lockout(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    client.application.config["TRUST_PROXY_HEADERS"] = False
    username = "spoofed_xff_lockout_admin"
    direct_ip = "198.51.100.50"

    _ensure_admin_user(session, username, TEST_ADMIN_PASSWORD)
    session.query(AdminLoginAttempt).delete()
    session.commit()

    responses = [
        client.post(
            "/admin/login",
            data={"username": username, "password": "wrong-password"},
            headers={"X-Forwarded-For": f"203.0.113.{attempt}"},
            environ_base={"REMOTE_ADDR": direct_ip},
            follow_redirects=False,
        )
        for attempt in range(1, 7)
    ]

    assert responses[-1].status_code == 429
    assert {
        row.ip for row in session.query(AdminLoginAttempt).filter_by(username=username)
    } == {direct_ip}


def test_trusted_proxy_uses_proxyfix_normalized_remote_addr(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    client.application.config["TRUST_PROXY_HEADERS"] = True
    username = "trusted_proxy_lockout_admin"
    forwarded_client_ip = "203.0.113.75"
    original_wsgi_app = client.application.wsgi_app
    client.application.wsgi_app = ProxyFix(original_wsgi_app, x_for=1)

    _ensure_admin_user(session, username, TEST_ADMIN_PASSWORD)
    session.query(AdminLoginAttempt).delete()
    session.commit()
    try:
        response = client.post(
            "/admin/login",
            data={"username": username, "password": "wrong-password"},
            headers={"X-Forwarded-For": forwarded_client_ip},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
            follow_redirects=False,
        )
    finally:
        client.application.wsgi_app = original_wsgi_app

    assert response.status_code in (302, 303)
    attempt = session.query(AdminLoginAttempt).filter_by(username=username).one()
    assert attempt.ip == forwarded_client_ip
