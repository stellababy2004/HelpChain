import pytest

from backend.models import AdminUser, Structure, db
from backend.helpchain_backend.src.models.magic_link_token import MagicLinkToken
from tests.test_admin_team import _admin, _login


def _capture_mail(monkeypatch):
    captured = {}

    def send(recipient, subject, template, context, **kwargs):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["template"] = template
        captured.update(context)
        return True

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        send,
    )
    return captured


def test_forgot_password_page_and_login_link(client):
    login = client.get("/admin/login")
    assert login.status_code == 200
    assert "/admin/forgot-password" in login.text

    page = client.get("/admin/forgot-password")
    assert page.status_code == 200
    assert 'name="identifier"' in page.text
    assert page.headers["Cache-Control"] == "no-store"


def test_forgot_password_known_account_sends_reset(
    client, app, monkeypatch
):
    structure = Structure(
        name="Recovery A",
        slug="recovery-a",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    user = _admin("recovery_admin", structure.id)
    db.session.commit()

    captured = _capture_mail(monkeypatch)

    response = client.post(
        "/admin/forgot-password",
        data={"identifier": user.email},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured["recipient"] == user.email
    assert "/team/reset-access#" in captured["magic_link_url"]

    token = MagicLinkToken.query.filter_by(
        purpose="admin_access_reset",
        email=user.email,
    ).one()

    assert token.used_at is None
    assert token.invalidated_at is None


def test_forgot_password_unknown_account_does_not_enumerate(
    client, monkeypatch
):
    def forbidden_mail(*args, **kwargs):
        pytest.fail("Unknown account must not send mail")

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        forbidden_mail,
    )

    response = client.post(
        "/admin/forgot-password",
        data={"identifier": "does-not-exist@example.test"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        "Si un compte actif correspond"
        in response.text
    )


def test_self_service_reset_is_single_use(
    client, monkeypatch
):
    structure = Structure(
        name="Recovery B",
        slug="recovery-b",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    user = _admin("self_reset_admin", structure.id)
    user.set_password("OldSecurePass123")
    db.session.commit()

    captured = _capture_mail(monkeypatch)

    client.post(
        "/admin/forgot-password",
        data={"identifier": user.email},
    )

    raw = captured["magic_link_url"].split("#", 1)[1]

    response = client.post(
        "/team/reset-access",
        data={
            "token": raw,
            "password": "NewSecurePass123",
            "confirm_password": "NewSecurePass123",
        },
    )

    assert response.status_code == 303

    db.session.expire_all()
    refreshed = db.session.get(AdminUser, user.id)
    assert refreshed.check_password("NewSecurePass123")

    reused = client.post(
        "/team/reset-access",
        data={
            "token": raw,
            "password": "AnotherSecurePass123",
            "confirm_password": "AnotherSecurePass123",
        },
    )

    assert reused.status_code == 400


def test_superadmin_can_issue_platform_reset(
    client, app, monkeypatch
):
    structure = Structure(
        name="Recovery C",
        slug="recovery-c",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    target = _admin("platform_target", structure.id)

    superadmin = _admin(
        "platform_superadmin",
        structure.id,
        "superadmin",
    )

    db.session.commit()
    _login(client, app, superadmin)

    captured = _capture_mail(monkeypatch)

    response = client.post(
        f"/admin/platform/users/{target.id}/reset-access"
    )

    assert response.status_code == 303
    assert captured["recipient"] == target.email
    assert "/team/reset-access#" in captured["magic_link_url"]


def test_authenticated_admin_can_change_own_password(client, app, monkeypatch):
    from backend.models import AdminUser, db

    with app.app_context():
        user = AdminUser(
            username="password_change_admin",
            email="password-change-admin@example.com",
            role="admin",
            is_active=True,
        )
        user.set_password("OldPassword1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, app, user)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "OldPassword1",
            "new_password": "NewPassword2",
            "confirm_password": "NewPassword2",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with app.app_context():
        user = db.session.get(AdminUser, user_id)
        assert user.check_password("NewPassword2")
        assert not user.check_password("OldPassword1")


def test_change_password_rejects_wrong_current_password(client, app):
    from backend.models import AdminUser, db

    with app.app_context():
        user = AdminUser(
            username="password_change_admin",
            email="password-change-admin@example.com",
            role="admin",
            is_active=True,
        )
        user.set_password("OldPassword1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, app, user)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "WrongPassword1",
            "new_password": "NewPassword2",
            "confirm_password": "NewPassword2",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(AdminUser, user_id)
        assert user.check_password("OldPassword1")


def test_change_password_rejects_confirmation_mismatch(client, app):
    from backend.models import AdminUser, db

    with app.app_context():
        user = AdminUser(
            username="password_change_admin",
            email="password-change-admin@example.com",
            role="admin",
            is_active=True,
        )
        user.set_password("OldPassword1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, app, user)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "OldPassword1",
            "new_password": "NewPassword2",
            "confirm_password": "DifferentPassword3",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(AdminUser, user_id)
        assert user.check_password("OldPassword1")


def test_change_password_enforces_password_policy(client, app):
    from backend.models import AdminUser, db

    with app.app_context():
        user = AdminUser(
            username="password_change_admin",
            email="password-change-admin@example.com",
            role="admin",
            is_active=True,
        )
        user.set_password("OldPassword1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, app, user)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "OldPassword1",
            "new_password": "weak",
            "confirm_password": "weak",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(AdminUser, user_id)
        assert user.check_password("OldPassword1")
