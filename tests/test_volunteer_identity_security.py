import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_admin_intervenant_detail_routes import _login_admin
from tests.test_admin_volunteer_membership import membership


def _identity_path(data):
    return f"/admin/admin_volunteers/edit/{data.volunteer.id}"


def _identity_payload():
    return {
        "name": "Identité mise à jour",
        "email": "updated-identity@example.test",
        "phone": "0102030405",
        "location": "Paris",
        "skills": "documents",
    }


def _link_identity(data, session, active=True):
    data.target.legacy_volunteer_id = data.volunteer.id
    data.target.is_active = active
    session.commit()


def _approve_identity_membership(data, session):
    from backend.models import VolunteerStructureMembership

    session.add(
        VolunteerStructureMembership(
            volunteer_id=data.volunteer.id,
            structure_id=data.structure.id,
            status="approved",
        )
    )
    session.commit()


@pytest.mark.parametrize("role", ["admin", "superadmin"])
@pytest.mark.parametrize("active_link", [True, False])
def test_own_structure_identity_edit_is_permitted(
    membership, session, app, role, active_link
):
    data = membership
    _approve_identity_membership(data, session)
    _link_identity(data, session, active_link)
    data.admin.role = role
    session.commit()
    _login_admin(data.client, app, data.admin)
    assert (
        data.client.post(_identity_path(data), data=_identity_payload()).status_code
        == 302
    )
    session.refresh(data.volunteer)
    assert data.volunteer.email == _identity_payload()["email"]
    assert data.target.legacy_volunteer_id == data.volunteer.id


@pytest.mark.parametrize(
    "restriction",
    [
        "cross_tenant",
        "attached_superadmin_cross_tenant",
        "readonly",
        "ops",
        "no_structure",
        "unlinked",
        "inactive_admin",
        "ambiguous",
    ],
)
def test_identity_edit_rejects_unauthorized_admin(
    membership, session, app, restriction
):
    from backend.models import Intervenant

    data = membership
    _approve_identity_membership(data, session)
    _link_identity(data, session)
    if restriction in {"cross_tenant", "attached_superadmin_cross_tenant"}:
        data.admin.structure_id = data.other_structure.id
        if restriction == "attached_superadmin_cross_tenant":
            data.admin.role = "superadmin"
    elif restriction in {"readonly", "ops"}:
        data.admin.role = restriction
    elif restriction == "no_structure":
        data.admin.structure_id = None
    elif restriction == "unlinked":
        data.target.legacy_volunteer_id = None
    elif restriction == "inactive_admin":
        data.admin.is_active = False
    else:
        session.add(
            Intervenant(
                structure_id=data.structure.id,
                legacy_volunteer_id=data.volunteer.id,
                actor_type="volunteer",
                is_active=False,
            )
        )
    session.commit()
    original = (data.volunteer.name, data.volunteer.email)
    _login_admin(data.client, app, data.admin)
    # Tenant scope is deliberately opaque.  The legacy Intervenant link is
    # not required for this route: it edits Volunteer identity fields and the
    # approved VolunteerStructureMembership is the authorization boundary.
    expected_status = (
        404
        if restriction
        in {
            "cross_tenant",
            "attached_superadmin_cross_tenant",
            "no_structure",
            "inactive_admin",
        }
        else 302
        if restriction in {"unlinked", "ambiguous"}
        else 403
    )
    assert (
        data.client.post(_identity_path(data), data=_identity_payload()).status_code
        == expected_status
    )
    session.refresh(data.volunteer)
    if expected_status == 302:
        assert data.volunteer.email == _identity_payload()["email"]
    else:
        assert (data.volunteer.name, data.volunteer.email) == original


def test_global_superadmin_can_edit_unlinked_identity(membership, session, app):
    data = membership
    _approve_identity_membership(data, session)
    _login_admin(data.client, app, data.global_admin)
    assert (
        data.client.post(_identity_path(data), data=_identity_payload()).status_code
        == 302
    )
    session.refresh(data.volunteer)
    assert data.volunteer.email == _identity_payload()["email"]
    assert data.target.legacy_volunteer_id is None


def _profile_path(data, scoped=True):
    prefix = f"/admin/structures/{data.structure.id}" if scoped else "/admin"
    return f"{prefix}/intervenants/{data.target.id}"


def _profile_payload(data, **changes):
    payload = {
        "name": data.target.name,
        "actor_type": "volunteer",
        "email": data.target.email,
        "availability": "available",
    }
    payload.update(changes)
    return payload


@pytest.mark.parametrize("scoped", [True, False])
def test_readonly_can_view_but_cannot_mutate_intervenant(
    membership, session, app, scoped
):
    data = membership
    _link_identity(data, session, active=False)
    data.target.availability = "unavailable"
    data.admin.role = "readonly"
    session.commit()
    _login_admin(data.client, app, data.admin)
    path = _profile_path(data, scoped)
    assert data.client.get(path).status_code == 200
    response = data.client.post(
        path,
        data=_profile_payload(
            data,
            actor_type="social_worker",
            legacy_volunteer_id="999999",
            structure_id=str(data.other_structure.id),
        ),
    )
    assert response.status_code == 403
    session.refresh(data.target)
    assert data.target.actor_type == "volunteer"
    assert data.target.is_active is False
    assert data.target.availability == "unavailable"
    assert data.target.legacy_volunteer_id == data.volunteer.id
    assert data.target.structure_id == data.structure.id


@pytest.mark.parametrize("global_admin", [True, False])
def test_authorized_admin_can_update_intervenant_profile(
    membership, session, app, global_admin
):
    data = membership
    _link_identity(data, session, active=False)
    _login_admin(data.client, app, data.global_admin if global_admin else data.admin)
    response = data.client.post(_profile_path(data), data=_profile_payload(data))
    assert response.status_code == 302
    session.refresh(data.target)
    assert data.target.actor_type == "volunteer"
    assert data.target.is_active is True
    assert data.target.legacy_volunteer_id == data.volunteer.id


@pytest.mark.parametrize("change", ["actor_type", "is_active", "inactive_admin"])
def test_profile_mutation_requires_authority_over_membership_fields(
    membership, session, app, change
):
    data = membership
    _link_identity(data, session)
    if change == "inactive_admin":
        data.admin.is_active = False
    else:
        data.admin.role = "ops"
    session.commit()
    _login_admin(data.client, app, data.admin)
    payload = _profile_payload(data)
    if change == "actor_type":
        payload["actor_type"] = "social_worker"
    elif change == "is_active":
        payload["availability"] = "unavailable"
    expected_status = 404 if change == "inactive_admin" else 403
    assert (
        data.client.post(_profile_path(data), data=payload).status_code
        == expected_status
    )
    session.refresh(data.target)
    assert data.target.actor_type == "volunteer"
    assert data.target.is_active is True


def test_ops_retains_non_membership_profile_editing(membership, session, app):
    data = membership
    _link_identity(data, session)
    data.admin.role = "ops"
    session.commit()
    _login_admin(data.client, app, data.admin)
    response = data.client.post(
        _profile_path(data),
        data=_profile_payload(
            data,
            name="Nom opérationnel",
            availability="busy",
        ),
    )
    assert response.status_code == 302
    session.refresh(data.target)
    assert data.target.name == "Nom opérationnel"
    assert data.target.is_active is True
    assert data.target.actor_type == "volunteer"


def test_readonly_cannot_create_intervenant_profile(membership, session, app):
    from backend.models import Intervenant

    data = membership
    data.admin.role = "readonly"
    session.commit()
    _login_admin(data.client, app, data.admin)
    count = session.query(Intervenant).count()
    assert data.client.get("/admin/intervenants/new").status_code == 200
    response = data.client.post(
        "/admin/intervenants/new",
        data={
            "full_name": "Non autorisé",
            "profession": "volunteer",
            "city": "Paris",
            "availability": "available",
            "structure_id": str(data.structure.id),
        },
    )
    assert response.status_code == 403
    assert session.query(Intervenant).count() == count


def _consume_volunteer_token(client, session, email):
    from backend.helpchain_backend.src.models.magic_link_token import MagicLinkToken

    raw = "identity-security-token"
    session.add(
        MagicLinkToken(
            purpose="volunteer",
            email=email,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    session.commit()
    return client.get(f"/auth/magic/{raw}")


@pytest.mark.parametrize("mailbox", ["alice_team", "alice%team"])
@pytest.mark.parametrize("existing_exact", [True, False])
def test_magic_link_email_wildcards_are_literal(
    client, session, mailbox, existing_exact
):
    from backend.models import Intervenant, Volunteer

    decoy = Volunteer(email="aliceXteam@example.test")
    exact_email = f"{mailbox}@example.test"
    session.add(decoy)
    session.flush()
    exact = Volunteer(email=exact_email) if existing_exact else None
    if exact is not None:
        session.add(exact)
    session.commit()
    response = _consume_volunteer_token(client, session, exact_email)
    assert response.status_code == 303
    with client.session_transaction() as sess:
        assert sess["volunteer_id"] != decoy.id
        selected_id = sess["volunteer_id"]
    selected = session.get(Volunteer, selected_id)
    assert selected.email == exact_email
    if exact is not None:
        assert selected_id == exact.id
    assert session.query(Volunteer).count() == 2
    assert session.query(Intervenant).count() == 0


def test_magic_link_normalizes_trim_and_case(client, session):
    from backend.models import Volunteer

    volunteer = Volunteer(email="  Mixed.Case@Example.test  ")
    session.add(volunteer)
    session.commit()
    response = _consume_volunteer_token(client, session, " MIXED.case@example.TEST ")
    assert response.status_code == 303
    with client.session_transaction() as sess:
        assert sess["volunteer_id"] == volunteer.id
    assert session.query(Volunteer).count() == 1


@pytest.mark.parametrize(
    "second_email", ["duplicate@example.test", " DUPLICATE@EXAMPLE.TEST "]
)
def test_magic_link_ambiguous_identity_authenticates_neither_account(
    client, session, second_email
):
    from backend.models import SecurityEvent, Volunteer

    first = Volunteer(email="duplicate@example.test")
    second = Volunteer(email=second_email)
    session.add_all([first, second])
    session.commit()
    with client.session_transaction() as sess:
        sess["volunteer_id"] = first.id
        sess["volunteer_logged_in"] = True
    response = _consume_volunteer_token(client, session, "duplicate@example.test")
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert not sess.get("volunteer_id")
        assert not sess.get("volunteer_logged_in")
    assert session.query(Volunteer).count() == 2
    rejected = (
        session.query(SecurityEvent).filter_by(event_type="magic_link_rejected").all()
    )
    assert any(
        (event.meta or {}).get("reason") == "ambiguous_identity" for event in rejected
    )
