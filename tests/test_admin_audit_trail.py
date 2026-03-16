from uuid import uuid4

from backend.models import AdminAuditEvent, Request, Structure, User


def _admin_id_from_client(client) -> int:
    with client.session_transaction() as sess:
        val = sess.get("admin_user_id") or sess.get("user_id") or sess.get("_user_id")
    return int(val)


def _create_request(session, *, owner_id=None, status="pending") -> Request:
    structure = session.query(Structure).filter_by(slug="default").first()
    suffix = uuid4().hex[:8]
    user = User(
        username=f"audit_user_{suffix}",
        email=f"audit_{suffix}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()

    req = Request(
        title=f"Audit request {suffix}",
        user_id=user.id,
        status=status,
        category="general",
        structure_id=getattr(structure, "id", None),
        owner_id=owner_id,
    )
    session.add(req)
    session.commit()
    return req


def test_admin_audit_status_change(authenticated_admin_client, session):
    client = authenticated_admin_client
    admin_id = _admin_id_from_client(client)
    req = _create_request(session, owner_id=admin_id, status="pending")

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        f"/admin/update_status/{req.id}",
        data={"status": "approved"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 200)

    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="STATUS_CHANGE", target_type="Request", target_id=req.id)
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    old_status = (event.payload or {}).get("old", {}).get("status")
    new_status = (event.payload or {}).get("new", {}).get("status")
    assert old_status in {"pending", "open"}
    assert new_status in {"approved", "in_progress"}


def test_admin_audit_assign_unassign_owner(authenticated_admin_client, session):
    client = authenticated_admin_client
    admin_id = _admin_id_from_client(client)
    req = _create_request(session, owner_id=None, status="pending")

    session.query(AdminAuditEvent).delete()
    session.commit()

    assign_resp = client.post(f"/admin/requests/{req.id}/assign", follow_redirects=False)
    assert assign_resp.status_code in (302, 303)
    unassign_resp = client.post(
        f"/admin/requests/{req.id}/unassign", follow_redirects=False
    )
    assert unassign_resp.status_code in (302, 303)

    assign_event = (
        session.query(AdminAuditEvent)
        .filter_by(action="ASSIGN_OPERATOR", target_type="Request", target_id=req.id)
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert assign_event is not None
    assert (assign_event.payload or {}).get("old", {}).get("owner_id") is None
    assert (assign_event.payload or {}).get("new", {}).get("owner_id") == admin_id

    unassign_event = (
        session.query(AdminAuditEvent)
        .filter_by(
            action="request.unassign_owner", target_type="Request", target_id=req.id
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert unassign_event is not None
    assert (unassign_event.payload or {}).get("old", {}).get("owner_id") == admin_id
    assert (unassign_event.payload or {}).get("new", {}).get("owner_id") is None
