#!/usr/bin/env python3
"""
Test admin login with email 2FA
"""

import pytest


def test_admin_login_ready_db_does_not_show_not_initialized(
    client, init_test_data, session
):
    """Smoke test for a repaired local DB with admin, structures, and requests."""
    from sqlalchemy import inspect

    from backend.models import AdminUser
    from backend.helpchain_backend.src.routes import admin as admin_routes

    inspector = inspect(session.get_bind())
    for table_name in ("admin_users", "structures", "requests"):
        assert inspector.has_table(table_name)
    assert session.query(AdminUser.id).first() is not None

    admin_routes._SCHEMA_TABLE_CACHE["admin_users"] = False
    try:
        resp = client.post(
            "/admin/login",
            data={"username": "missing-admin", "password": "wrong"},
            follow_redirects=True,
        )
    finally:
        admin_routes._SCHEMA_TABLE_CACHE.pop("admin_users", None)

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Database not initialized" not in html
    assert "Run dev_bootstrap.py" not in html


def test_admin_login_using_client(client, init_test_data):
    """Use the Flask test client and fixtures instead of an external HTTP call.

    This keeps the test deterministic inside pytest: it uses the same
    app, database and session fixtures as the rest of the suite.
    """
    # Ensure the app will use email 2FA flow for this test
    client.application.config["EMAIL_2FA_ENABLED"] = True

    # Use the seeded admin_with_2fa from init_test_data
    admin = init_test_data["admin_with_2fa"]

    # GET the login page
    resp = client.get("/admin/login")
    assert resp.status_code == 200

    # POST credentials for the admin that has 2FA enabled, including CSRF token from session
    with client.session_transaction() as sess:
        csrf_token = sess.get("csrf_token", "")

    login_data = {
        "username": admin.username,
        "password": "TestPass123",
        "csrf_token": csrf_token,
    }
    resp = client.post("/admin/login", data=login_data, follow_redirects=False)
    assert (
        resp.status_code == 302
    ), f"Expected redirect after POST, got {resp.status_code}"

    location = resp.headers.get("Location", "")
    # Should redirect into the 2FA flow
    assert "/admin/2fa" in location

    # Check that the session was populated for pending email 2FA
    with client.session_transaction() as sess:
        assert sess.get("pending_email_2fa") is True
        assert sess.get("email_2fa_code") is not None
