from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest

from backend.models import AdminUser, Structure


TEST_PASSWORD = "MasterE2ePass1"


def _make_admin(
    session,
    *,
    role: str,
    structure_id: int | None,
    mfa_enabled: bool = False,
) -> AdminUser:
    suffix = uuid4().hex[:10]
    admin = AdminUser(
        username=f"master-e2e-{role}-{suffix}",
        email=f"master-e2e-{role}-{suffix}@test.local",
        role=role,
        structure_id=structure_id,
        is_active=True,
        mfa_enabled=mfa_enabled,
        totp_secret=pyotp.random_base32() if mfa_enabled else None,
    )
    admin.set_password(TEST_PASSWORD)
    session.add(admin)
    session.commit()
    return admin


def _structure(session) -> Structure:
    structure = Structure(
        name=f"Master E2E Structure {uuid4().hex[:8]}",
        slug=f"master-e2e-{uuid4().hex[:10]}",
        status="active",
    )
    session.add(structure)
    session.commit()
    return structure


def test_real_admin_login_mfa_role_change_deactivation_and_logout(app, session):
    structure = _structure(session)
    admin = _make_admin(
        session,
        role="admin",
        structure_id=structure.id,
        mfa_enabled=True,
    )
    client = app.test_client()

    login_response = client.post(
        "/admin/login",
        data={"username": admin.username, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert login_response.status_code in (302, 303)
    assert "/admin/mfa/verify" in (login_response.headers.get("Location") or "")

    before_mfa = client.get("/admin/home", follow_redirects=False)
    assert before_mfa.status_code in (302, 303)
    assert "/admin/mfa/verify" in (before_mfa.headers.get("Location") or "")

    verify_response = client.post(
        "/admin/mfa/verify",
        data={"code": pyotp.TOTP(admin.totp_secret).now()},
        follow_redirects=False,
    )
    assert verify_response.status_code in (302, 303)

    after_mfa = client.get("/admin/home", follow_redirects=False)
    assert after_mfa.status_code == 200

    admin.role = "readonly"
    session.commit()
    role_changed = client.get("/admin/requests", follow_redirects=False)
    assert role_changed.status_code == 403

    admin.role = "admin"
    session.commit()
    logout_response = client.get("/admin/logout", follow_redirects=False)
    assert logout_response.status_code in (302, 303)
    after_logout = client.get("/admin/home", follow_redirects=False)
    assert after_logout.status_code in (302, 303, 401, 403, 404)

    relogin_response = client.post(
        "/admin/login",
        data={"username": admin.username, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert "/admin/mfa/verify" in (relogin_response.headers.get("Location") or "")
    client.post(
        "/admin/mfa/verify",
        data={"code": pyotp.TOTP(admin.totp_secret).now()},
        follow_redirects=False,
    )

    admin.is_active = False
    session.commit()
    deactivated = client.get("/admin/home", follow_redirects=False)
    assert deactivated.status_code in (302, 303, 401, 403, 404)


@pytest.mark.parametrize(
    ("role", "structure_attached", "mfa_required"),
    (
        ("readonly", True, False),
        ("ops", True, False),
        ("admin", True, True),
        ("superadmin", False, True),
    ),
)
def test_real_login_role_matrix(
    app, session, role, structure_attached, mfa_required
):
    structure = _structure(session) if structure_attached else None
    admin = _make_admin(
        session,
        role=role,
        structure_id=structure.id if structure else None,
        mfa_enabled=mfa_required,
    )
    client = app.test_client()

    login_response = client.post(
        "/admin/login",
        data={"username": admin.username, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert login_response.status_code in (302, 303)
    location = login_response.headers.get("Location") or ""

    if mfa_required:
        assert "/admin/mfa/verify" in location
        verify_response = client.post(
            "/admin/mfa/verify",
            data={"code": pyotp.TOTP(admin.totp_secret).now()},
            follow_redirects=False,
        )
        assert verify_response.status_code in (302, 303)
    else:
        assert "/ops/workspace" in location

    response = client.get("/ops/workspace", follow_redirects=False)
    assert response.status_code == 200


def test_operator_required_rejects_session_flags_without_authenticated_admin(
    app, db_schema,
):
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["admin_logged_in"] = True
        flask_session["is_admin"] = True
        flask_session["role"] = "ops"

    response = client.get("/ops/workspace", follow_redirects=False)
    assert response.status_code in (302, 303, 401, 403, 404)
