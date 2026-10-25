from __future__ import annotations

import json
import pytest


def _login_admin(client, admin_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["user_id"] = admin_user.id
        sess["role"] = admin_user.role
        sess["is_authenticated"] = True
        sess["is_admin"] = True
        sess["admin_logged_in"] = True
        sess["admin_id"] = admin_user.id
        sess["mfa_required"] = True
        sess["mfa_ok_until"] = "4102444800"
        sess["admin_mfa_last_verified"] = 4102444800
        sess["admin_mfa_user_id"] = admin_user.id


def _make_structure(session, *, name="Structure Client", slug="structure-client"):
    from backend.models import Structure

    structure = Structure(name=name, slug=slug, status="active")
    session.add(structure)
    session.commit()
    return structure


def _make_admin(
    session,
    *,
    username,
    email,
    role="admin",
    structure_id=None,
    must_change_password=False,
    onboarding_step=None,
    onboarding_completed_at=None,
):
    from backend.models import AdminUser

    admin = AdminUser(
        username=username,
        email=email,
        password_hash="x",
        role=role,
        is_active=True,
        structure_id=structure_id,
        must_change_password=must_change_password,
        onboarding_step=onboarding_step,
        onboarding_completed_at=onboarding_completed_at,
    )
    session.add(admin)
    session.commit()
    return admin


def test_new_structure_admin_redirected_to_onboarding(client, session):
    structure = _make_structure(session)
    admin = _make_admin(
        session,
        username="client_admin",
        email="client_admin@test.local",
        structure_id=structure.id,
        must_change_password=True,
        onboarding_step="welcome",
    )
    _login_admin(client, admin)

    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302 or response.status_code == 303
    assert response.headers.get("Location", "").endswith("/admin/onboarding")


def test_completed_onboarding_admin_can_access_dashboard(client, session):
    from backend.models import utc_now

    structure = _make_structure(session, name="Structure Ready", slug="structure-ready")
    admin = _make_admin(
        session,
        username="client_ready",
        email="client_ready@test.local",
        structure_id=structure.id,
        must_change_password=False,
        onboarding_step="complete",
        onboarding_completed_at=utc_now(),
    )
    _login_admin(client, admin)

    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302 or response.status_code == 303
    assert "/admin/onboarding" not in (response.headers.get("Location") or "")


def test_superadmin_not_trapped_in_client_onboarding(client, session):
    admin = _make_admin(
        session,
        username="global_superadmin",
        email="global_superadmin@test.local",
        role="superadmin",
        structure_id=None,
        must_change_password=True,
        onboarding_step="welcome",
    )
    _login_admin(client, admin)

    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302 or response.status_code == 303
    assert "/admin/onboarding" not in (response.headers.get("Location") or "")


def test_password_change_step_validates_confirmation_mismatch(client, session):
    structure = _make_structure(session, name="Structure Password", slug="structure-password")
    admin = _make_admin(
        session,
        username="client_password",
        email="client_password@test.local",
        structure_id=structure.id,
        must_change_password=True,
        onboarding_step="secure_access",
    )
    _login_admin(client, admin)

    response = client.post(
        "/admin/onboarding/step",
        data={
            "step": "secure_access",
            "new_password": "SecurePass123",
            "confirm_password": "DifferentPass123",
        },
        follow_redirects=False,
    )

    session.refresh(admin)
    assert response.status_code == 302 or response.status_code == 303
    assert response.headers.get("Location", "").endswith("/admin/onboarding")
    assert admin.must_change_password is True
    assert admin.onboarding_step == "secure_access"


def test_onboarding_complete_sets_completed_at(client, session):
    structure = _make_structure(session, name="Structure Finish", slug="structure-finish")
    admin = _make_admin(
        session,
        username="client_finish",
        email="client_finish@test.local",
        structure_id=structure.id,
        must_change_password=False,
        onboarding_step="complete",
    )
    _login_admin(client, admin)

    response = client.post("/admin/onboarding/complete", data={}, follow_redirects=False)

    session.refresh(admin)
    assert response.status_code == 302 or response.status_code == 303
    assert admin.onboarding_completed_at is not None


def test_onboarding_completion_review_shows_canonical_workspace_summary(client, session):
    structure = _make_structure(session, name="Review Structure", slug="review-structure")
    structure.city = "Paris"
    structure.organization_type = "ccas"
    admin = _make_admin(
        session,
        username="review_admin",
        email="review-admin@test.local",
        structure_id=structure.id,
        onboarding_step="complete",
    )
    admin.onboarding_data_json = json.dumps(
        {"structure_setup": {"name": "Review Structure", "city": "Paris"}, "team_invites": {"sent": True}}
    )
    session.commit()
    _login_admin(client, admin)

    response = client.get("/admin/onboarding")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Review Structure" in html
    assert "Paris" in html
    assert "CCAS" in html
    assert "Demandes" in html
    assert "social_support" not in html
    assert "review-admin@test.local" in html
    assert "envoyees" in html
    assert "edit=structure_setup" in html


def test_onboarding_completion_review_can_edit_structure_setup(client, session):
    structure = _make_structure(session, name="Editable Structure", slug="editable-structure")
    admin = _make_admin(
        session,
        username="editable_admin",
        email="editable-admin@test.local",
        structure_id=structure.id,
        onboarding_step="complete",
    )
    _login_admin(client, admin)

    response = client.get("/admin/onboarding?edit=structure_setup")

    assert response.status_code == 200
    assert b'name="organization_type"' in response.data
    session.refresh(admin)
    assert admin.onboarding_step == "complete"


def _post_structure_setup(client, *, organization_type):
    return client.post(
        "/admin/onboarding/step",
        data={
            "step": "structure_setup",
            "structure_name": "Structure Type Test",
            "city": "Paris",
            "team_size": "1-5",
            "main_need": "suivi dossiers",
            "organization_type": organization_type,
        },
        follow_redirects=False,
    )


def test_onboarding_persists_canonical_organization_type(client, session):
    from backend.helpchain_backend.src.services.adaptive_experience import (
        adaptive_modules,
        module_enabled,
        organization_capabilities,
    )

    structure = _make_structure(session, name="Type Persist", slug="type-persist")
    admin = _make_admin(
        session,
        username="type_persist_admin",
        email="type-persist@test.local",
        structure_id=structure.id,
        onboarding_step="structure_setup",
    )
    _login_admin(client, admin)

    response = _post_structure_setup(client, organization_type="ccas")

    session.refresh(structure)
    assert response.status_code in (302, 303)
    assert structure.organization_type == "ccas"
    assert organization_capabilities(structure) == (
        "social_support",
        "emergency_assistance",
    )
    modules = adaptive_modules(structure)
    assert "cases" in modules
    assert "referrals" in modules
    assert module_enabled(structure, "cases")
    assert module_enabled(structure, "referrals")
    assert not module_enabled(structure, "platform")


@pytest.mark.parametrize("organization_type", ["", "unsupported_type"])
def test_onboarding_rejects_missing_or_unknown_organization_type(
    client, session, organization_type
):
    structure = _make_structure(
        session,
        name=f"Type Invalid {organization_type or 'missing'}",
        slug=f"type-invalid-{organization_type or 'missing'}",
    )
    admin = _make_admin(
        session,
        username=f"type_invalid_{organization_type or 'missing'}",
        email=f"type-invalid-{organization_type or 'missing'}@test.local",
        structure_id=structure.id,
        onboarding_step="structure_setup",
    )
    _login_admin(client, admin)

    response = _post_structure_setup(client, organization_type=organization_type)

    session.refresh(structure)
    assert response.status_code in (302, 303)
    assert response.headers.get("Location", "").endswith("/admin/onboarding")
    assert structure.organization_type in (None, "")


def test_onboarding_structure_setup_with_type_continues_existing_flow(client, session):
    structure = _make_structure(session, name="Flow Type", slug="flow-type")
    admin = _make_admin(
        session,
        username="flow_type_admin",
        email="flow-type@test.local",
        structure_id=structure.id,
        onboarding_step="structure_setup",
    )
    _login_admin(client, admin)

    response = _post_structure_setup(client, organization_type="association")

    session.refresh(admin)
    assert response.status_code in (302, 303)
    assert response.headers.get("Location", "").endswith("/admin/onboarding")
    assert admin.onboarding_step == "invite_team"
