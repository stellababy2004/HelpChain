import json
import re
from types import SimpleNamespace

import pytest

from tests.test_admin_intervenant_detail_routes import (
    _login_admin,
    _seed_intervenant_route_data,
)


@pytest.fixture
def membership(app, session, init_test_data):
    from backend.models import Volunteer

    structure, other_structure, target, other, global_admin, admin = (
        _seed_intervenant_route_data(session)
    )
    target.actor_type = "volunteer"
    volunteer = Volunteer(
        name="Compte bénévole confirmé", email="membership@example.test"
    )
    session.add(volunteer)
    session.commit()
    client = app.test_client()
    _login_admin(client, app, admin)
    return SimpleNamespace(
        client=client,
        admin=admin,
        global_admin=global_admin,
        structure=structure,
        other_structure=other_structure,
        target=target,
        other=other,
        volunteer=volunteer,
    )


def _path(data, scoped=True):
    prefix = f"/admin/structures/{data.structure.id}" if scoped else "/admin"
    return f"{prefix}/intervenants/{data.target.id}"


def _payload(data, **overrides):
    payload = {
        "intervenant_action": "link_volunteer",
        "structure_id": str(data.structure.id),
        "volunteer_id": str(data.volunteer.id),
        "confirm_volunteer": str(data.volunteer.id),
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_genuine_volunteer_actor(membership, session):
    from backend.models import Intervenant

    page = membership.client.get("/admin/intervenants/new")
    assert 'value="volunteer"' in page.get_data(as_text=True)
    response = membership.client.post(
        "/admin/intervenants/new",
        data={
            "full_name": "Bénévole opérationnel",
            "profession": "volunteer",
            "email": "canonical-volunteer@example.test",
            "city": "Paris",
            "availability": "available",
            "structure_id": str(membership.structure.id),
        },
    )
    assert response.status_code == 302
    actor = (
        session.query(Intervenant)
        .filter_by(email="canonical-volunteer@example.test")
        .one()
    )
    assert actor.actor_type == "volunteer"
    assert actor.structure_id == membership.structure.id
    assert actor.legacy_volunteer_id is None


@pytest.mark.parametrize("scoped", [True, False])
def test_authorized_admin_can_link_with_identity_preview(membership, session, scoped):
    from backend.models import IntervenantActivity, Volunteer

    data = membership
    path = _path(data, scoped)
    page = data.client.get(path)
    assert data.volunteer.email not in page.get_data(as_text=True)
    preview = data.client.get(
        path, query_string={"link_volunteer_id": data.volunteer.id}
    )
    html = preview.get_data(as_text=True)
    assert "Lier un compte bénévole" in html
    assert data.volunteer.name in html
    assert data.volunteer.email in html
    assert data.structure.name in html
    count = session.query(Volunteer).count()
    response = data.client.post(path, data=_payload(data))
    assert response.status_code == 303
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id == data.volunteer.id
    assert session.query(Volunteer).count() == count
    event = (
        session.query(IntervenantActivity)
        .filter_by(intervenant_id=data.target.id, event_type="volunteer_account_linked")
        .one()
    )
    assert event.actor_admin_id == data.admin.id
    assert event.structure_id == data.structure.id
    assert json.loads(event.meta_json) == {
        "volunteer_id": data.volunteer.id,
        "intervenant_id": data.target.id,
        "structure_id": data.structure.id,
        "result": "linked",
    }


def test_link_is_idempotent_without_reactivating_actor(membership, session):
    from backend.models import IntervenantActivity

    data = membership
    data.target.is_active = False
    data.target.availability = "unavailable"
    data.volunteer.is_active = False
    session.commit()
    for _ in range(2):
        assert data.client.post(_path(data), data=_payload(data)).status_code == 303
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id == data.volunteer.id
    assert data.target.is_active is False
    assert data.target.availability == "unavailable"
    session.refresh(data.volunteer)
    assert data.volunteer.is_active is False
    events = (
        session.query(IntervenantActivity)
        .filter_by(intervenant_id=data.target.id, event_type="volunteer_account_linked")
        .order_by(IntervenantActivity.id)
        .all()
    )
    assert [json.loads(event.meta_json)["result"] for event in events] == [
        "linked",
        "already_linked",
    ]


@pytest.mark.parametrize("inactive", [False, True])
@pytest.mark.parametrize("same_structure", [False, True])
def test_existing_volunteer_link_blocks_another_actor(
    membership, session, inactive, same_structure
):
    from backend.models import Intervenant, IntervenantActivity

    data = membership
    previous = Intervenant(
        actor_type="volunteer",
        legacy_volunteer_id=data.volunteer.id,
        structure_id=data.structure.id if same_structure else data.other_structure.id,
        is_active=not inactive,
    )
    session.add(previous)
    session.commit()
    assert data.client.post(_path(data), data=_payload(data)).status_code == 409
    session.refresh(data.target)
    session.refresh(previous)
    assert data.target.legacy_volunteer_id is None
    assert previous.legacy_volunteer_id == data.volunteer.id
    assert (
        session.query(IntervenantActivity)
        .filter_by(event_type="volunteer_account_linked")
        .count()
        == 0
    )


def test_target_cannot_be_reassigned_to_another_volunteer(
    membership, session, init_test_data
):
    data = membership
    data.target.legacy_volunteer_id = init_test_data["volunteer"].id
    session.commit()
    assert data.client.post(_path(data), data=_payload(data)).status_code == 409
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id == init_test_data["volunteer"].id


def test_professional_cannot_receive_volunteer_link(membership, session):
    data = membership
    data.target.actor_type = "social_worker"
    session.commit()
    assert data.client.post(_path(data), data=_payload(data)).status_code == 409
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


@pytest.mark.parametrize("role", ["admin", "superadmin"])
def test_cross_tenant_admin_cannot_link(membership, session, app, role):
    data = membership
    data.admin.role = role
    data.admin.structure_id = data.other_structure.id
    session.commit()
    _login_admin(data.client, app, data.admin)
    assert data.client.post(_path(data), data=_payload(data)).status_code == 403
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("structure_id", "", 400),
        ("structure_id", "999999", 403),
        ("volunteer_id", "999999", 404),
        ("confirm_volunteer", "", 400),
        ("confirm_volunteer", "999999", 400),
    ],
)
def test_link_requires_explicit_valid_identity_and_structure(
    membership, session, field, value, status
):
    data = membership
    payload = _payload(data, **{field: value})
    if field == "volunteer_id":
        payload["confirm_volunteer"] = value
    response = data.client.post(_path(data), data=payload)
    assert response.status_code == status
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


@pytest.mark.parametrize("role", ["readonly", "ops"])
def test_non_membership_admin_roles_cannot_link(membership, session, app, role):
    data = membership
    data.admin.role = role
    session.commit()
    _login_admin(data.client, app, data.admin)
    response = data.client.post(_path(data), data=_payload(data))
    assert response.status_code == 403
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


def test_link_requires_csrf(membership, app, session):
    data = membership
    app.config["WTF_CSRF_ENABLED"] = True
    path = _path(data)
    assert data.client.post(path, data=_payload(data)).status_code == 400
    page = data.client.get(path, query_string={"link_volunteer_id": data.volunteer.id})
    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', page.get_data(as_text=True)
    )
    assert token
    response = data.client.post(path, data=_payload(data, csrf_token=token.group(1)))
    assert response.status_code == 303


def test_membership_service_checks_scope_without_tenant_fallback(
    membership, app, session
):
    from flask import session as flask_session
    from backend.helpchain_backend.src.services.volunteer_membership import (
        VolunteerLinkError,
        link_volunteer_to_intervenant,
    )

    data = membership
    data.admin.structure_id = None
    session.commit()
    with app.test_request_context():
        flask_session.update(admin_logged_in=True, admin_id=data.admin.id)
        with pytest.raises(VolunteerLinkError) as error:
            link_volunteer_to_intervenant(
                volunteer_id=data.volunteer.id,
                intervenant_id=data.target.id,
                structure_id=data.structure.id,
                confirmed=True,
            )
        assert error.value.status_code == 403
    assert data.target.legacy_volunteer_id is None


def test_platform_global_admin_links_only_explicit_target(membership, app, session):
    data = membership
    _login_admin(data.client, app, data.global_admin)
    assert data.client.post(_path(data), data=_payload(data)).status_code == 303
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id == data.volunteer.id


def test_duplicate_email_identities_require_manual_review(membership, session):
    from backend.models import Volunteer

    data = membership
    duplicate = Volunteer(
        name="Autre compte", email=f" {data.volunteer.email.upper()} "
    )
    session.add(duplicate)
    session.commit()
    assert data.client.post(_path(data), data=_payload(data)).status_code == 409
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


@pytest.mark.parametrize(
    "failure", ["anonymous", "cross_tenant", "wrong_target_structure", "missing_target"]
)
def test_service_independently_validates_administrator_and_target(
    membership, app, session, failure
):
    from flask import session as flask_session
    from backend.helpchain_backend.src.services.volunteer_membership import (
        VolunteerLinkError,
        link_volunteer_to_intervenant,
    )

    data = membership
    structure_id = data.structure.id
    target_id = data.target.id
    if failure == "cross_tenant":
        data.admin.structure_id = data.other_structure.id
        session.commit()
    elif failure == "wrong_target_structure":
        target_id = data.other.id
    elif failure == "missing_target":
        target_id = 999999
    with app.test_request_context():
        if failure != "anonymous":
            flask_session.update(admin_logged_in=True, admin_id=data.admin.id)
        with pytest.raises(VolunteerLinkError) as error:
            link_volunteer_to_intervenant(
                volunteer_id=data.volunteer.id,
                intervenant_id=target_id,
                structure_id=structure_id,
                confirmed=True,
            )
        assert error.value.status_code == (404 if failure == "missing_target" else 403)
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


def test_link_locks_only_identity_and_target_for_postgres(membership, session):
    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql

    statements = []

    def capture_locks(connection, statement, multiparams, params, execution_options):
        if getattr(statement, "_for_update_arg", None) is not None:
            statements.append(str(statement.compile(dialect=postgresql.dialect())))

    engine = session.get_bind()
    event.listen(engine, "before_execute", capture_locks)
    try:
        response = membership.client.post(_path(membership), data=_payload(membership))
    finally:
        event.remove(engine, "before_execute", capture_locks)
    assert response.status_code == 303
    assert len(statements) == 2
    assert "FOR UPDATE OF volunteers" in statements[0]
    assert "FOR UPDATE OF intervenants" in statements[1]


def test_link_and_audit_roll_back_together(membership, session):
    from sqlalchemy import event
    from backend.models import IntervenantActivity

    data = membership

    def fail_audit(mapper, connection, target):
        if target.event_type == "volunteer_account_linked":
            raise RuntimeError("audit unavailable")

    event.listen(IntervenantActivity, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            data.client.post(_path(data), data=_payload(data))
    finally:
        event.remove(IntervenantActivity, "before_insert", fail_audit)
    session.refresh(data.target)
    assert data.target.legacy_volunteer_id is None


def test_admin_link_grants_only_canonical_structure_access(membership, session, app):
    from backend.models import Request
    from backend.helpchain_backend.src.services.matching_v1 import _MATCH_CACHE

    data = membership
    data.volunteer.location = "Paris"
    data.volunteer.skills = "documents logement transport"
    data.volunteer.availability = "weekends"
    data.volunteer.volunteer_onboarded = True
    own = Request(
        title="documents logement transport",
        city="Paris",
        priority="urgent",
        status="open",
        structure_id=data.structure.id,
    )
    other = Request(
        title="documents logement transport",
        city="Paris",
        priority="urgent",
        status="open",
        structure_id=data.other_structure.id,
    )
    session.add_all([own, other])
    session.commit()
    assert data.client.post(_path(data), data=_payload(data)).status_code == 303
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["volunteer_id"] = data.volunteer.id
    _MATCH_CACHE.clear()
    page = client.get("/volunteer/dashboard")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert f"/volunteer/requests/{own.id}/help" in html
    assert f"/volunteer/requests/{other.id}/help" not in html
    assert client.post(f"/volunteer/requests/{own.id}/help").status_code == 303
    assert client.post(f"/volunteer/requests/{other.id}/help").status_code == 404
