import pytest

from backend.helpchain_backend.src.authz import can_volunteer_access_request
from backend.models import Request, Structure, User, Volunteer, VolunteerStructureMembership
from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest


def _subject(session):
    structure_a = Structure(name="Guard A", slug="guard-a")
    structure_b = Structure(name="Guard B", slug="guard-b")
    account = User(
        username="guard-volunteer",
        email="guard-volunteer@test.local",
        password_hash="test",
        is_active=True,
    )
    session.add_all([structure_a, structure_b, account])
    session.flush()
    volunteer = Volunteer(name="Guard Volunteer", user_id=account.id, is_active=True)
    session.add(volunteer)
    session.flush()
    request_a = Request(title="Request A", structure_id=structure_a.id, status="open")
    request_b = Request(title="Request B", structure_id=structure_b.id, status="open")
    session.add_all([request_a, request_b])
    session.flush()
    return account, volunteer, structure_a, structure_b, request_a, request_b


def _membership(session, volunteer_id, structure_id, status):
    row = VolunteerStructureMembership(
        volunteer_id=volunteer_id, structure_id=structure_id, status=status
    )
    session.add(row)
    session.flush()
    return row


def test_guard_requires_approved_membership_and_object_permission(session):
    account, volunteer, structure_a, structure_b, request_a, request_b = _subject(session)
    _membership(session, volunteer.id, structure_a.id, "approved")

    assert not can_volunteer_access_request(volunteer, request_a, session)
    interest = VolunteerInterest(
        volunteer_id=volunteer.id, request_id=request_a.id, status="pending"
    )
    session.flush()
    assert not can_volunteer_access_request(volunteer, request_a, session)
    request_a.assigned_volunteer_id = volunteer.id
    session.flush()
    assert can_volunteer_access_request(volunteer, request_a, session)
    assert not can_volunteer_access_request(volunteer, request_b, session)


@pytest.mark.parametrize("status", ["pending", "suspended", "revoked"])
def test_guard_rejects_non_approved_membership(session, status):
    account, volunteer, structure_a, _structure_b, request_a, _request_b = _subject(session)
    _membership(session, volunteer.id, structure_a.id, status)
    request_a.assigned_volunteer_id = volunteer.id
    session.flush()
    assert not can_volunteer_access_request(volunteer, request_a, session)


def test_guard_rechecks_open_session_revocation_and_account_state(session):
    account, volunteer, structure_a, _structure_b, request_a, _request_b = _subject(session)
    membership = _membership(session, volunteer.id, structure_a.id, "approved")
    request_a.assigned_volunteer_id = volunteer.id
    session.flush()
    assert can_volunteer_access_request(volunteer, request_a, session)

    membership.status = "revoked"
    session.flush()
    assert not can_volunteer_access_request(volunteer, request_a, session)

    membership.status = "approved"
    account.is_active = False
    session.flush()
    assert not can_volunteer_access_request(volunteer, request_a, session)


def test_guard_rejects_inactive_volunteer_and_forged_structure(session):
    account, volunteer, structure_a, structure_b, request_a, request_b = _subject(session)
    _membership(session, volunteer.id, structure_a.id, "approved")
    request_a.assigned_volunteer_id = volunteer.id
    request_b.assigned_volunteer_id = volunteer.id
    session.flush()
    assert can_volunteer_access_request(volunteer, request_a, session)
    assert not can_volunteer_access_request(volunteer, request_b, session)

    volunteer.is_active = False
    session.flush()
    assert not can_volunteer_access_request(volunteer, request_a, session)
