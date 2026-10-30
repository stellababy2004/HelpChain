import pytest
import re

from backend.models import Request, VolunteerStructureMembership
from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest


def _setup(session, init_test_data, *, membership_status="approved", request_status="open"):
    volunteer = init_test_data["volunteer"]
    structure = init_test_data["structure"]
    req = Request(
        title="B3.2.8 request",
        status=request_status,
        structure_id=structure.id,
    )
    session.add(req)
    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=structure.id,
            status=membership_status,
        )
    )
    session.commit()
    return volunteer, structure, req


def test_help_creates_pending_interest_without_duplicate(app, session, init_test_data, authenticated_volunteer_client):
    volunteer, _structure, req = _setup(session, init_test_data)
    client = authenticated_volunteer_client

    response = client.post(f"/volunteer/requests/{req.id}/help")
    assert response.status_code == 303
    interest = VolunteerInterest.query.filter_by(
        volunteer_id=volunteer.id, request_id=req.id
    ).one()
    assert interest.status == "pending"

    response = client.post(f"/volunteer/requests/{req.id}/help")
    assert response.status_code == 303
    assert VolunteerInterest.query.filter_by(
        volunteer_id=volunteer.id, request_id=req.id
    ).count() == 1


@pytest.mark.parametrize("status", ["pending", "suspended", "revoked"])
def test_help_rejects_non_approved_membership_without_mutation(
    session, init_test_data, authenticated_volunteer_client, status
):
    volunteer, _structure, req = _setup(session, init_test_data, membership_status=status)
    response = authenticated_volunteer_client.post(f"/volunteer/requests/{req.id}/help")
    assert response.status_code == 404
    assert VolunteerInterest.query.filter_by(
        volunteer_id=volunteer.id, request_id=req.id
    ).count() == 0


@pytest.mark.parametrize("path", ["seen", "dismiss"])
def test_seen_and_dismiss_require_current_membership_and_are_personal(
    session, init_test_data, authenticated_volunteer_client, path
):
    volunteer, structure, req = _setup(session, init_test_data)
    response = authenticated_volunteer_client.post(
        f"/volunteer/requests/{req.id}/{path}"
    )
    assert response.status_code == 200
    assert req.structure_id == structure.id

    membership = VolunteerStructureMembership.query.filter_by(
        volunteer_id=volunteer.id, structure_id=structure.id
    ).one()
    membership.status = "revoked"
    session.commit()
    response = authenticated_volunteer_client.post(
        f"/volunteer/requests/{req.id}/{path}"
    )
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["help", "seen", "dismiss"])
def test_remaining_volunteer_actions_require_csrf(app, session, init_test_data, authenticated_volunteer_client, path):
    app.config["WTF_CSRF_ENABLED"] = True
    _volunteer, _structure, req = _setup(session, init_test_data)
    response = authenticated_volunteer_client.post(
        f"/volunteer/requests/{req.id}/{path}"
    )
    assert response.status_code == 400


def _rendered_csrf_token(client, request_id):
    page = client.get(f"/volunteer/requests/{request_id}")
    match = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', page.get_data(as_text=True))
    assert match, "CSRF token not rendered"
    return match.group(1)


@pytest.mark.parametrize("path", ["help", "seen", "dismiss"])
def test_remaining_volunteer_actions_reject_invalid_csrf(
    app, session, init_test_data, authenticated_volunteer_client, path
):
    app.config["WTF_CSRF_ENABLED"] = True
    _volunteer, _structure, req = _setup(session, init_test_data)
    response = authenticated_volunteer_client.post(
        f"/volunteer/requests/{req.id}/{path}",
        data={"csrf_token": "invalid-token"},
    )
    assert response.status_code == 400
    assert VolunteerInterest.query.filter_by(request_id=req.id).count() == 0


@pytest.mark.parametrize("path", ["help", "seen", "dismiss"])
def test_valid_csrf_does_not_bypass_revoked_membership(
    app, session, init_test_data, authenticated_volunteer_client, path
):
    app.config["WTF_CSRF_ENABLED"] = True
    volunteer, structure, req = _setup(session, init_test_data)
    session.add(
        VolunteerInterest(
            volunteer_id=volunteer.id,
            request_id=req.id,
            status="approved",
        )
    )
    session.commit()
    token = _rendered_csrf_token(authenticated_volunteer_client, req.id)
    membership = VolunteerStructureMembership.query.filter_by(
        volunteer_id=volunteer.id, structure_id=structure.id
    ).one()
    membership.status = "revoked"
    session.commit()

    response = authenticated_volunteer_client.post(
        f"/volunteer/requests/{req.id}/{path}",
        data={"csrf_token": token},
    )
    assert response.status_code == 404
    assert VolunteerInterest.query.filter_by(request_id=req.id).count() == 1
