"""Tests for locale selection logic and admin login/logout.

These tests import the main `app` module (app.py) to exercise the new
_select_locale IP + cookie + Accept-Language priority and the admin
authentication flow.
"""

from __future__ import annotations

import os
import re

import pytest

from app import _select_locale, app  # type: ignore


@pytest.fixture(scope="module")
def client():
    with app.app_context():  # ensure DB and tables exist
        try:
            from models import AdminUser, db
        except Exception:
            from backend.models import AdminUser, db  # type: ignore
        db.create_all()
        # Seed admin user with known password
        if not AdminUser.query.filter_by(username="admin").first():
            admin = AdminUser(username="admin", email="admin@example.com")
            admin.set_password(os.getenv("ADMIN_USER_PASSWORD", "Admin12345!"))
            db.session.add(admin)
            db.session.commit()
    yield app.test_client()


def test_locale_ip_fr():
    with app.test_request_context("/", headers={"CF-IPCountry": "FR"}):
        assert _select_locale() == "fr"


def test_locale_ip_bg():
    with app.test_request_context("/", headers={"CF-IPCountry": "BG"}):
        assert _select_locale() == "bg"


def test_locale_ip_other_defaults_en():
    with app.test_request_context("/", headers={"CF-IPCountry": "DE"}):
        assert _select_locale() == "en"


def test_locale_accept_language_fallback():
    # No geo header, Accept-Language determines best match
    hdr = {"Accept-Language": "bg,en;q=0.8,fr;q=0.7"}
    with app.test_request_context("/", headers=hdr):
        assert _select_locale() == "bg"


def test_admin_login_logout_flow(client):
    # Login with seeded credentials
    resp = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": os.getenv("ADMIN_USER_PASSWORD", "Admin12345!"),
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    # Session should have admin_logged_in
    with client.session_transaction() as sess:
        assert sess.get("admin_logged_in") is True

    # Logout
    logout_resp = client.post("/logout", follow_redirects=False)
    assert logout_resp.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess.get("admin_logged_in") is None
