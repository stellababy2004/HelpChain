from datetime import datetime, timedelta, timezone

from flask import Flask
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.helpchain_backend.src.jwt_utils import (
    encode_access_token,
    encode_refresh_token,
)
from backend.helpchain_backend.src.models import ProfessionalLead, RefreshToken
from backend.models import AdminUser, Structure, Volunteer


def _admin(*, username, role, structure_id=None):
    return AdminUser(
        username=username,
        email=f"{username}@test.local",
        password_hash=generate_password_hash("TestPassword1"),
        role=role,
        is_active=True,
        structure_id=structure_id,
    )


def test_proposal_routes_do_not_disclose_leads_to_anonymous_client(client):
    assert client.get("/admin/proposal/1").status_code == 404
    assert client.get("/admin/proposal-clean/1").status_code == 404


def test_platform_global_admin_keeps_proposal_access(client, app):
    with app.app_context():
        lead = ProfessionalLead(
            organization="Synthetic partner",
            email="partner@test.local",
            profession="synthetic",
        )
        admin = _admin(username="proposal_global_admin", role="superadmin")
        db.session.add_all([lead, admin])
        db.session.commit()
        admin_id = admin.id
        lead_id = lead.id

    with client.session_transaction() as session:
        session["admin_logged_in"] = True
        session["admin_user_id"] = admin_id

    assert client.get(f"/admin/proposal/{lead_id}").status_code == 200
    assert client.get(f"/admin/proposal-clean/{lead_id}").status_code == 200


def test_legacy_proposal_engine_registration_rejects_anonymous_client():
    from backend.proposal_engine import register_proposal_engine

    legacy_app = Flask(__name__)
    register_proposal_engine(legacy_app)
    assert legacy_app.test_client().get("/admin/proposal/1").status_code == 404


def test_tenant_admin_cannot_query_global_nearby_volunteer_directory(client, app):
    app.config["MFA_ENABLED"] = False
    with app.app_context():
        structure = Structure(name="Scoped", slug="scoped")
        admin = _admin(username="scoped_api_admin", role="admin", structure_id=None)
        db.session.add_all([structure, admin])
        db.session.flush()
        admin.structure_id = structure.id
        db.session.commit()
        token = encode_access_token(admin.id)

    response = client.get(
        "/api/volunteers/nearby?lat=42.7&lng=23.3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_platform_global_admin_keeps_nearby_directory_access(client, app):
    app.config["MFA_ENABLED"] = False
    with app.app_context():
        admin = _admin(username="global_api_admin", role="superadmin")
        db.session.add(admin)
        db.session.commit()
        token = encode_access_token(admin.id)

    response = client.get(
        "/api/volunteers/nearby?lat=42.7&lng=23.3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_volunteer_location_update_requires_record_owner_or_global_admin(client, app):
    with app.app_context():
        volunteer = Volunteer(name="Owned volunteer", latitude=1.0, longitude=2.0)
        db.session.add(volunteer)
        db.session.commit()
        volunteer_id = volunteer.id

    with client.session_transaction() as session:
        session["volunteer_logged_in"] = True
        session["volunteer_id"] = volunteer_id + 1

    denied = client.put(
        f"/api/volunteers/{volunteer_id}/location",
        json={"latitude": 3.0, "longitude": 4.0},
    )
    assert denied.status_code == 403

    with client.session_transaction() as session:
        session["volunteer_id"] = volunteer_id

    allowed = client.put(
        f"/api/volunteers/{volunteer_id}/location",
        json={"latitude": 3.0, "longitude": 4.0},
    )
    assert allowed.status_code == 200


def test_platform_global_admin_can_update_volunteer_location(client, app):
    app.config["MFA_ENABLED"] = False
    with app.app_context():
        volunteer = Volunteer(name="Global update", latitude=1.0, longitude=2.0)
        admin = _admin(username="global_location_admin", role="superadmin")
        db.session.add_all([volunteer, admin])
        db.session.commit()
        volunteer_id = volunteer.id
        token = encode_access_token(admin.id)

    response = client.put(
        f"/api/volunteers/{volunteer_id}/location",
        json={"latitude": 3.0, "longitude": 4.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_tenant_admin_id_collision_cannot_update_volunteer_location(client, app):
    with app.app_context():
        volunteer = Volunteer(
            name="Collision target", user_id=1, latitude=1.0, longitude=2.0
        )
        tenant = Structure(name="Collision tenant", slug="collision-tenant")
        admin = _admin(username="collision_admin", role="admin", structure_id=None)
        db.session.add_all([volunteer, tenant, admin])
        db.session.flush()
        admin.structure_id = tenant.id
        db.session.commit()
        volunteer_id = volunteer.id
        admin_id = admin.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["admin_logged_in"] = True
        session["admin_user_id"] = admin_id

    response = client.put(
        f"/api/volunteers/{volunteer_id}/location",
        json={"latitude": 3.0, "longitude": 4.0},
    )
    assert response.status_code == 403


def test_existing_mfa_required_access_token_is_rejected(client, app):
    with app.app_context():
        admin = _admin(username="mfa_access_admin", role="admin")
        db.session.add(admin)
        db.session.commit()
        token = encode_access_token(admin.id)

    response = client.get(
        "/api/volunteers/nearby?lat=42.7&lng=23.3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "MFA required"}


def test_api_password_login_denies_roles_requiring_mfa(client, app):
    with app.app_context():
        admin = _admin(username="mfa_api_admin", role="admin")
        db.session.add(admin)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"username": "mfa_api_admin", "password": "TestPassword1"},
    )
    assert response.status_code == 403
    assert response.get_json() == {"error": "mfa_required"}


def test_api_refresh_denies_existing_token_for_mfa_required_role(client, app):
    with app.app_context():
        admin = _admin(username="mfa_refresh_admin", role="admin")
        db.session.add(admin)
        db.session.flush()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            hours=1
        )
        refresh_jti = "test-refresh-token-that-is-long-enough"
        db.session.add(
            RefreshToken(user_id=admin.id, jti=refresh_jti, expires_at=expires_at)
        )
        db.session.commit()
        refresh_token = encode_refresh_token(admin.id, refresh_jti, expires_at)

    response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
    assert response.get_json() == {"error": "refresh_revoked"}


def test_api_password_login_keeps_non_mfa_role_contract(client, app):
    with app.app_context():
        admin = _admin(username="ops_api_admin", role="ops")
        db.session.add(admin)
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"username": "ops_api_admin", "password": "TestPassword1"},
    )
    assert response.status_code == 200
    assert "access_token" in response.get_json()
