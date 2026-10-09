from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.helpchain_backend.src.models import Case, ProfessionalLead
from backend.models import AdminUser, Assignment, Intervenant, Request, Structure, User, utc_now

pytestmark = pytest.mark.spine


def _login_superadmin(client, app, admin: AdminUser) -> None:
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin.id)
        sess["user_id"] = admin.id
        sess["admin_id"] = admin.id
        sess["admin_user_id"] = admin.id
        sess["role"] = admin.role
        sess["is_authenticated"] = True
        sess["is_admin"] = True
        sess["admin_logged_in"] = True
        sess["mfa_required"] = True
        sess[app.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
        sess["mfa_ok_until"] = (utc_now() + timedelta(minutes=30)).isoformat()
        sess["admin_mfa_last_verified"] = 4102444800
        sess["admin_mfa_user_id"] = admin.id


def _make_admin(session, *, username: str = "lead_convert_admin") -> AdminUser:
    admin = AdminUser(
        username=username,
        email=f"{username}@test.local",
        password_hash="x",
        role="superadmin",
        is_active=True,
        mfa_enabled=True,
        totp_secret="lead-conversion-test",
    )
    session.add(admin)
    session.flush()
    return admin


def _make_structure(session, *, slug: str = "lead-conversion-target") -> Structure:
    structure = Structure(name=slug.replace("-", " ").title(), slug=slug)
    session.add(structure)
    session.flush()
    return structure


def _make_lead(
    session,
    *,
    email: str = "marie.dupont@example.test",
    status: str = "qualified",
    full_name: str = "Marie Dupont",
) -> ProfessionalLead:
    lead = ProfessionalLead(
        email=email,
        full_name=full_name,
        phone="0102030405",
        city="Paris",
        profession="social_worker",
        organization="Maison test",
        source="test",
        status=status,
    )
    session.add(lead)
    session.flush()
    return lead


def _conversion_url(lead: ProfessionalLead) -> str:
    return f"/admin/professional-leads/{lead.id}/convert-intervenant"


def test_qualified_lead_conversion_creates_unavailable_intervenant_and_link(app, session):
    structure = _make_structure(session)
    lead = _make_lead(session)
    admin = _make_admin(session)
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    response = client.post(
        _conversion_url(lead),
        data={"structure_id": str(structure.id)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(lead)
    intervenant = session.get(Intervenant, lead.intervenant_id)
    assert intervenant is not None
    assert response.headers["Location"].endswith(f"/admin/intervenants/{intervenant.id}")
    assert intervenant.structure_id == structure.id
    assert intervenant.name == "Marie Dupont"
    assert intervenant.email == "marie.dupont@example.test"
    assert intervenant.actor_type == "social_worker"
    assert intervenant.availability == "unavailable"
    assert intervenant.is_active is False


def test_non_qualified_lead_conversion_is_rejected(app, session):
    structure = _make_structure(session)
    lead = _make_lead(session, status="contacted")
    admin = _make_admin(session, username="lead_convert_reject_admin")
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    response = client.post(
        _conversion_url(lead),
        data={"structure_id": str(structure.id)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(lead)
    assert lead.intervenant_id is None
    assert session.query(Intervenant).filter_by(structure_id=structure.id).count() == 0


def test_conversion_requires_target_structure(app, session):
    lead = _make_lead(session, email="missing.structure@example.test")
    admin = _make_admin(session, username="lead_convert_missing_structure_admin")
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    response = client.post(_conversion_url(lead), data={}, follow_redirects=False)

    assert response.status_code == 303
    session.refresh(lead)
    assert lead.intervenant_id is None
    assert session.query(Intervenant).count() == 0


def test_double_conversion_redirects_existing_intervenant_without_duplicate(app, session):
    structure = _make_structure(session)
    lead = _make_lead(session, email="double.convert@example.test")
    admin = _make_admin(session, username="lead_convert_idempotent_admin")
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    first = client.post(_conversion_url(lead), data={"structure_id": str(structure.id)})
    session.refresh(lead)
    intervenant_id = lead.intervenant_id
    second = client.post(_conversion_url(lead), data={"structure_id": str(structure.id)})

    assert first.status_code == 303
    assert second.status_code == 303
    assert session.query(Intervenant).filter_by(email="double.convert@example.test").count() == 1
    assert second.headers["Location"].endswith(f"/admin/intervenants/{intervenant_id}")


def test_conversion_blocks_existing_same_email_in_same_structure(app, session):
    structure = _make_structure(session)
    lead = _make_lead(session, email="duplicate@example.test")
    existing = Intervenant(
        structure_id=structure.id,
        name="Existing Intervenant",
        actor_type="social_worker",
        email=" Duplicate@Example.Test ",
        availability="available",
        is_active=True,
    )
    admin = _make_admin(session, username="lead_convert_duplicate_admin")
    session.add(existing)
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    response = client.post(
        _conversion_url(lead),
        data={"structure_id": str(structure.id)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(lead)
    assert lead.intervenant_id is None
    assert session.query(Intervenant).filter_by(structure_id=structure.id).count() == 1


def test_professional_lead_detail_shows_conversion_states(app, session):
    structure = _make_structure(session)
    new_lead = _make_lead(session, email="new.state@example.test", status="new")
    qualified_lead = _make_lead(session, email="qualified.state@example.test")
    converted_lead = _make_lead(session, email="converted.state@example.test")
    intervenant = Intervenant(
        structure_id=structure.id,
        name="Converted State",
        actor_type="field_referent",
        email="converted.state@example.test",
        availability="unavailable",
        is_active=False,
    )
    session.add(intervenant)
    session.flush()
    converted_lead.intervenant_id = intervenant.id
    admin = _make_admin(session, username="lead_convert_ui_admin")
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    new_page = client.get(f"/admin/professional-leads/{new_lead.id}")
    qualified_page = client.get(f"/admin/professional-leads/{qualified_lead.id}")
    converted_page = client.get(f"/admin/professional-leads/{converted_lead.id}")

    assert new_page.status_code == 200
    assert b"Qualification requise avant conversion" in new_page.data
    assert b"Convertir en intervenant" not in new_page.data
    assert qualified_page.status_code == 200
    assert b"Convertir en intervenant" in qualified_page.data
    assert b"Structure cible" in qualified_page.data
    assert converted_page.status_code == 200
    assert b"Voir l'intervenant" in converted_page.data


def test_conversion_does_not_change_legacy_case_professional_assignment(app, session):
    structure = _make_structure(session)
    user = User(
        username="lead_conversion_requester",
        email="lead-conversion-requester@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
        structure_id=structure.id,
    )
    session.add(user)
    session.flush()
    request_row = Request(
        title="Legacy professional lead assignment",
        description="Keep assigned_professional_lead_id stable.",
        category="general",
        user_id=user.id,
        structure_id=structure.id,
        status="open",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(request_row)
    session.flush()
    lead = _make_lead(session, email="legacy.case.assignment@example.test")
    case_row = Case(
        request_id=request_row.id,
        structure_id=structure.id,
        status="assigned",
        assigned_professional_lead_id=lead.id,
    )
    admin = _make_admin(session, username="lead_convert_case_admin")
    session.add(case_row)
    session.commit()
    client = app.test_client()
    _login_superadmin(client, app, admin)

    response = client.post(
        _conversion_url(lead),
        data={"structure_id": str(structure.id)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(case_row)
    session.refresh(lead)
    assert case_row.assigned_professional_lead_id == lead.id
    assert lead.intervenant_id is not None
    assert session.query(Assignment).count() == 0
