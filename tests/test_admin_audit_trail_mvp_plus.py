from uuid import uuid4

from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest
from backend.models import AdminAuditEvent, Request, Structure, User, Volunteer


def _admin_id_from_client(client) -> int:
    with client.session_transaction() as sess:
        val = (
            sess.get("admin_user_id")
            or sess.get("admin_id")
            or sess.get("user_id")
            or sess.get("_user_id")
        )
    return int(val)


def _create_request(session, *, owner_id=None, status="pending") -> Request:
    structure = session.query(Structure).filter_by(slug="default").first()
    suffix = uuid4().hex[:8]
    user = User(
        username=f"audit_req_user_{suffix}",
        email=f"audit_req_{suffix}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()

    req = Request(
        title=f"Audit req {suffix}",
        user_id=user.id,
        status=status,
        category="general",
        structure_id=getattr(structure, "id", None),
        owner_id=owner_id,
    )
    session.add(req)
    session.commit()
    return req


def _create_interest(session, req_id: int, *, status="pending") -> VolunteerInterest:
    suffix = uuid4().hex[:8]
    volunteer = Volunteer(
        name=f"Audit Volunteer {suffix}",
        email=f"audit_vol_{suffix}@test.local",
        is_active=True,
    )
    session.add(volunteer)
    session.flush()

    interest = VolunteerInterest(
        volunteer_id=volunteer.id,
        request_id=req_id,
        status=status,
    )
    session.add(interest)
    session.commit()
    return interest


def test_admin_audit_request_unlock(authenticated_admin_client, session):
    client = authenticated_admin_client
    admin_id = _admin_id_from_client(client)
    req = _create_request(session, owner_id=admin_id, status="pending")

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(f"/admin/requests/{req.id}/unlock", follow_redirects=False)
    assert resp.status_code in (302, 303)

    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="request.unlock", target_type="Request", target_id=req.id)
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    payload = event.payload or {}
    assert payload.get("req_id") == req.id
    assert payload.get("old", {}).get("locked") is True
    assert payload.get("new", {}).get("locked") is False
    assert payload.get("old", {}).get("owner_id") == admin_id
    assert payload.get("new", {}).get("owner_id") is None


def test_admin_audit_interest_approve(authenticated_admin_client, session):
    client = authenticated_admin_client
    req = _create_request(session, owner_id=None, status="pending")
    interest = _create_interest(session, req_id=req.id, status="pending")

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        f"/admin/requests/{req.id}/interests/{interest.id}/approve",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    event = (
        session.query(AdminAuditEvent)
        .filter_by(
            action="interest.approve",
            target_type="Interest",
            target_id=interest.id,
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    payload = event.payload or {}
    assert payload.get("req_id") == req.id
    assert payload.get("interest_id") == interest.id
    assert payload.get("old", {}).get("status") == "pending"
    assert payload.get("new", {}).get("status") == "approved"


def test_admin_audit_interest_reject(authenticated_admin_client, session):
    client = authenticated_admin_client
    req = _create_request(session, owner_id=None, status="pending")
    interest = _create_interest(session, req_id=req.id, status="pending")

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        f"/admin/requests/{req.id}/interests/{interest.id}/reject",
        data={"reason": "Not a fit"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    event = (
        session.query(AdminAuditEvent)
        .filter_by(
            action="interest.reject",
            target_type="Interest",
            target_id=interest.id,
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    payload = event.payload or {}
    assert payload.get("req_id") == req.id
    assert payload.get("interest_id") == interest.id
    assert payload.get("old", {}).get("status") == "pending"
    assert payload.get("new", {}).get("status") == "rejected"
    assert payload.get("reason") == "Not a fit"
