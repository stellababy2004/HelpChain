from __future__ import annotations


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
