import re
import pytest

from backend.models import Notification, Request, VolunteerStructureMembership


def _notification_fixture(session, init_test_data, *, status="approved"):
    volunteer = init_test_data["volunteer"]
    structure = init_test_data["structure"]
    req = Request(title="Notification request", status="open", structure_id=structure.id)
    session.add(req)
    session.flush()
    membership = VolunteerStructureMembership(
        volunteer_id=volunteer.id, structure_id=structure.id, status=status
    )
    notif = Notification(
        volunteer_id=volunteer.id,
        request_id=req.id,
        type="new_match",
        title="Sensitive notification title",
        body="Sensitive notification body",
    )
    session.add_all([membership, notif])
    session.commit()
    return volunteer, structure, req, membership, notif


def test_notifications_list_and_counter_require_approved_membership(
    session, init_test_data, authenticated_volunteer_client
):
    _volunteer, _structure, _req, membership, notif = _notification_fixture(
        session, init_test_data
    )
    page = authenticated_volunteer_client.get("/volunteer/notifications")
    assert page.status_code == 200
    assert b"Sensitive notification title" in page.data
    assert b"Unread 1" in page.data
    membership.status = "revoked"
    session.commit()
    page = authenticated_volunteer_client.get("/volunteer/notifications")
    assert page.status_code == 200
    assert b"Sensitive notification title" not in page.data
    assert b"Sensitive notification body" not in page.data
    assert b"Unread 1" not in page.data


@pytest.mark.parametrize("status", ["pending", "suspended", "revoked"])
def test_non_approved_memberships_hide_request_notifications(
    session, init_test_data, authenticated_volunteer_client, status
):
    _volunteer, _structure, _req, _membership, _notif = _notification_fixture(
        session, init_test_data, status=status
    )
    page = authenticated_volunteer_client.get("/volunteer/notifications")
    assert page.status_code == 200
    assert b"Sensitive notification title" not in page.data


def test_absent_membership_hides_request_notifications(
    session, init_test_data, authenticated_volunteer_client
):
    volunteer = init_test_data["volunteer"]
    structure = init_test_data["structure"]
    session.query(VolunteerStructureMembership).filter_by(
        volunteer_id=volunteer.id, structure_id=structure.id
    ).delete(synchronize_session=False)
    req = Request(title="Unlinked request", status="open", structure_id=structure.id)
    session.add(req)
    session.flush()
    notif = Notification(
        volunteer_id=volunteer.id,
        request_id=req.id,
        type="new_match",
        title="Unlinked sensitive title",
        body="Unlinked sensitive body",
    )
    session.add(notif)
    session.commit()
    page = authenticated_volunteer_client.get("/volunteer/notifications")
    assert page.status_code == 200
    assert b"Unlinked sensitive title" not in page.data


def test_direct_notification_open_refuses_revoked_membership_without_mutation(
    session, init_test_data, authenticated_volunteer_client
):
    volunteer, _structure, _req, membership, notif = _notification_fixture(
        session, init_test_data
    )
    membership.status = "revoked"
    session.commit()
    before = (notif.is_read, notif.read_at)
    response = authenticated_volunteer_client.post(
        f"/volunteer/notifications/{notif.id}/open"
    )
    assert response.status_code == 404
    session.refresh(notif)
    assert (notif.is_read, notif.read_at) == before


def test_notifications_without_request_remain_owner_only(
    session, init_test_data, authenticated_volunteer_client
):
    volunteer = init_test_data["volunteer"]
    notif = Notification(
        volunteer_id=volunteer.id,
        request_id=None,
        type="system",
        title="Account notification",
        body="No request is attached.",
    )
    session.add(notif)
    session.commit()
    page = authenticated_volunteer_client.get("/volunteer/notifications")
    assert page.status_code == 200
    assert b"Account notification" in page.data


def test_notification_open_requires_csrf_and_valid_token_does_not_bypass_membership(
    app, session, init_test_data, authenticated_volunteer_client
):
    app.config["WTF_CSRF_ENABLED"] = True
    _volunteer, _structure, _req, membership, notif = _notification_fixture(
        session, init_test_data
    )

    before = (notif.is_read, notif.read_at)
    assert authenticated_volunteer_client.post(
        f"/volunteer/notifications/{notif.id}/open"
    ).status_code == 400
    assert authenticated_volunteer_client.post(
        f"/volunteer/notifications/{notif.id}/open",
        data={"csrf_token": "invalid-token"},
    ).status_code == 400
    session.refresh(notif)
    assert (notif.is_read, notif.read_at) == before

    page = authenticated_volunteer_client.get("/volunteer/notifications")
    token_match = re.search(
        r'name="csrf_token"[^>]+value="([^"]+)"', page.get_data(as_text=True)
    )
    assert token_match, "CSRF token not rendered"
    response = authenticated_volunteer_client.post(
        f"/volunteer/notifications/{notif.id}/open",
        data={"csrf_token": token_match.group(1)},
    )
    assert response.status_code in (302, 303)
    session.refresh(notif)
    assert notif.is_read is True

    membership.status = "revoked"
    session.commit()
    before = (notif.is_read, notif.read_at)
    response = authenticated_volunteer_client.post(
        f"/volunteer/notifications/{notif.id}/open",
        data={"csrf_token": token_match.group(1)},
    )
    assert response.status_code == 404
    session.refresh(notif)
    assert (notif.is_read, notif.read_at) == before
