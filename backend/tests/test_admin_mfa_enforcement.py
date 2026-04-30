from urllib.parse import parse_qs, urlparse

import pyotp
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.models import AdminUser


ADMIN_PASSWORD = "SecurePass123"


def _create_admin(*, username: str, secret: str) -> AdminUser:
    admin = AdminUser(
        username=username,
        email=f"{username}@test.local",
        password_hash=generate_password_hash(ADMIN_PASSWORD),
        role="admin",
        is_active=True,
        mfa_enabled=True,
        totp_secret=secret,
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def _login_password_only(client, username: str, *, next_url: str = "/admin/home"):
    return client.post(
        "/admin/login",
        data={
            "username": username,
            "password": ADMIN_PASSWORD,
            "next": next_url,
        },
        follow_redirects=False,
    )


def test_password_only_login_does_not_grant_admin_session(client, app):
    app.config["MFA_ENABLED"] = True
    app.config["REQUIRE_ADMIN_MFA"] = True

    with app.app_context():
        admin = _create_admin(
            username="mfa_gate_admin",
            secret=pyotp.random_base32(),
        )
        admin_id = admin.id

    response = _login_password_only(client, "mfa_gate_admin")

    assert response.status_code in {302, 303}
    assert "/admin/mfa/verify" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("admin_logged_in") is not True
        assert sess.get("pending_admin_user_id") == admin_id
        assert sess.get("admin_password_verified") is True
        assert sess.get("mfa_required") is True


def test_password_only_login_is_redirected_to_mfa_for_admin_home(client, app):
    app.config["MFA_ENABLED"] = True
    app.config["REQUIRE_ADMIN_MFA"] = True

    with app.app_context():
        _create_admin(
            username="mfa_redirect_admin",
            secret=pyotp.random_base32(),
        )

    _login_password_only(client, "mfa_redirect_admin")
    response = client.get("/admin/home", follow_redirects=False)

    assert response.status_code in {302, 303}
    parsed = urlparse(response.headers["Location"])
    assert parsed.path.endswith("/admin/mfa/verify")
    assert parse_qs(parsed.query).get("next") == ["/admin/home"]


def test_successful_mfa_grants_admin_access(client, app):
    app.config["MFA_ENABLED"] = True
    app.config["REQUIRE_ADMIN_MFA"] = True
    secret = pyotp.random_base32()

    with app.app_context():
        _create_admin(username="mfa_success_admin", secret=secret)

    _login_password_only(client, "mfa_success_admin")
    response = client.post(
        "/admin/mfa/verify?next=/admin/home",
        data={"code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code in {302, 303}
    assert urlparse(response.headers["Location"]).path == "/admin/home"

    with client.session_transaction() as sess:
        assert sess.get("admin_logged_in") is True
        assert sess.get("pending_admin_user_id") is None
        assert sess.get("admin_password_verified") is None


def test_external_next_is_sanitized_for_login_and_mfa_redirects(client, app):
    app.config["MFA_ENABLED"] = True
    app.config["REQUIRE_ADMIN_MFA"] = True
    secret = pyotp.random_base32()

    with app.app_context():
        _create_admin(username="mfa_next_admin", secret=secret)

    login_response = _login_password_only(
        client,
        "mfa_next_admin",
        next_url="https://evil.example/phish",
    )
    login_redirect = urlparse(login_response.headers["Location"])
    login_next = parse_qs(login_redirect.query).get("next", [""])

    assert login_response.status_code in {302, 303}
    assert login_redirect.path.endswith("/admin/mfa/verify")
    assert len(login_next) == 1
    assert (
        login_next[0] == ""
        or login_next[0].startswith("/admin")
    )
    assert "evil.example" not in login_next[0]
    assert not login_next[0].startswith(("http://", "https://", "//"))

    verify_response = client.post(
        "/admin/mfa/verify?next=https://evil.example/phish",
        data={"code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    verify_redirect = urlparse(verify_response.headers["Location"])

    assert verify_response.status_code in {302, 303}
    assert verify_redirect.path != "/phish"
    assert verify_redirect.netloc == ""
