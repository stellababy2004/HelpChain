from __future__ import annotations

from datetime import UTC, datetime
import os

from backend.models import AdminUser, Request, Structure, db
import pytest


def _submit_public_request(client, unique_suffix: str) -> str:
    title = f"Smoke request {unique_suffix}"
    payload = {
        "name": "Smoke User",
        "email": f"smoke.{unique_suffix}@test.local",
        "phone": "0600000000",
        "category": "social",
        "urgency": "normal",
        "title": title,
        "description": "Demande de test smoke pour verifier le flux complet.",
        "location_text": "Paris",
        "privacy_consent": "1",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }

    preview = client.post("/submit_request", data=payload, follow_redirects=False)
    assert preview.status_code == 200

    confirm = client.post("/submit_request/confirm", data={}, follow_redirects=False)
    assert confirm.status_code in (302, 303)

    return title


@pytest.fixture
def admin_ops_client(app, session):
    app.config["EMAIL_2FA_ENABLED"] = False
    # Test-only credential to avoid secret-like hardcoded values in fixtures.
    password = os.environ.get("TEST_ADMIN_PASSWORD", "test-password")
    admin = session.query(AdminUser).filter_by(email="admin.ops@test.local").first()
    if not admin:
        admin = AdminUser(
            username="admin_ops_smoke",
            email="admin.ops@test.local",
            password_hash="",
            role="admin",
            is_active=True,
        )
        admin.set_password(password)
        session.add(admin)
        session.commit()
    else:
        admin.role = "admin"
        admin.is_active = True
        admin.set_password(password)
        session.commit()

    client = app.test_client()
    login_resp = client.post(
        "/admin/login",
        data={"username": admin.username, "password": password},
        follow_redirects=False,
    )
    assert login_resp.status_code in (302, 303)
    return client


def test_public_create_persists_in_expected_structure(app, client, session):
    suffix = str(int(datetime.now(UTC).timestamp()))
    title = _submit_public_request(client, suffix)

    created = session.query(Request).filter_by(title=title).order_by(Request.id.desc()).first()
    assert created is not None
    assert created.structure_id is not None
    assert created.deleted_at is None

    default_structure = session.query(Structure).filter_by(slug="default").first()
    assert default_structure is not None
    assert created.structure_id == default_structure.id


def test_created_request_visible_in_admin_list_and_detail(admin_ops_client, client, session):
    suffix = str(int(datetime.now(UTC).timestamp()))
    title = _submit_public_request(client, suffix)

    created = session.query(Request).filter_by(title=title).order_by(Request.id.desc()).first()
    assert created is not None

    list_resp = admin_ops_client.get("/admin/requests")
    assert list_resp.status_code == 200
    assert title in list_resp.get_data(as_text=True)

    detail_resp = admin_ops_client.get(f"/admin/requests/{created.id}")
    assert detail_resp.status_code == 200


def test_inline_status_update_persists_for_created_request(admin_ops_client, client, session):
    suffix = str(int(datetime.now(UTC).timestamp()))
    title = _submit_public_request(client, suffix)

    created = session.query(Request).filter_by(title=title).order_by(Request.id.desc()).first()
    assert created is not None

    detail_resp = admin_ops_client.get(f"/admin/requests/{created.id}")
    assert detail_resp.status_code == 200

    resp = admin_ops_client.post(
        f"/admin/requests/{created.id}/status",
        data={"status": "in_progress"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    session.expire_all()
    refreshed = session.get(Request, created.id)
    assert refreshed is not None
    assert refreshed.status == "in_progress"


def test_smoke_uses_test_sqlalchemy_database(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    assert uri
    assert "sqlite" in uri

    with app.app_context():
        engine_db = str(getattr(db.engine.url, "database", "") or "")
    assert engine_db
    assert engine_db.endswith(".sqlite") or engine_db.endswith(".db")
