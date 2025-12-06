#!/usr/bin/env python3


def test_enable_2fa_persists(db_session, test_admin_user):
    """Enabling 2FA via the model should persist secret and flag."""
    from backend.models import AdminUser

    admin = test_admin_user
    # Ensure starting state
    assert not getattr(admin, "two_factor_enabled", False)

    secret = admin.enable_2fa()
    db_session.add(admin)
    db_session.commit()

    reloaded = db_session.get(AdminUser, admin.id)
    assert reloaded.two_factor_enabled is True
    assert reloaded.two_factor_secret is not None
    assert reloaded.two_factor_secret == secret


def test_login_with_2fa_redirects(client, init_test_data):
    """Posting credentials for an admin with TOTP 2FA should redirect to /admin/2fa."""
    admin = init_test_data["admin_with_2fa"]

    # Ensure email 2FA is disabled for this test
    client.application.config["EMAIL_2FA_ENABLED"] = False

    login_data = {"username": admin.username, "password": "TestPass123"}
    resp = client.post("/admin/login", data=login_data, follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "/admin/2fa" in location

    # session should contain pending_admin_id (or legacy key)
    with client.session_transaction() as sess:
        assert sess.get("pending_admin_id") or sess.get("pending_admin_user_id")


def test_disable_2fa_clears_secret(db_session, test_admin_user):
    """Disabling 2FA should clear secret and flag in the DB."""
    from backend.models import AdminUser

    admin = test_admin_user
    secret = admin.enable_2fa()
    db_session.add(admin)
    db_session.commit()

    # Now disable
    admin.disable_2fa()
    db_session.add(admin)
    db_session.commit()

    reloaded = db_session.get(AdminUser, admin.id)
    assert reloaded.two_factor_enabled is False
    assert reloaded.two_factor_secret in (None, "")
