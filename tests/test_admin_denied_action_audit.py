from uuid import uuid4

from backend.models import AdminAuditEvent, AdminUser, Request, Structure, User


def _admin_id_from_client(client) -> int:
    with client.session_transaction() as sess:
        val = (
            sess.get("admin_user_id")
            or sess.get("admin_id")
            or sess.get("user_id")
            or sess.get("_user_id")
        )
    return int(val)


def _set_current_admin_role(session, client, role: str) -> AdminUser:
    admin_id = _admin_id_from_client(client)
    admin = session.get(AdminUser, admin_id)
    admin.role = role
    session.commit()
    return admin


def _create_request(session) -> Request:
    structure = session.query(Structure).filter_by(slug="default").first()
    suffix = uuid4().hex[:8]
    user = User(
        username=f"deny_req_user_{suffix}",
        email=f"deny_req_{suffix}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()

    req = Request(
        title=f"Denied request {suffix}",
        user_id=user.id,
        status="pending",
        category="general",
        structure_id=getattr(structure, "id", None),
    )
    session.add(req)
    session.commit()
    return req


def test_ops_denied_archive_is_logged(authenticated_admin_client, session):
    client = authenticated_admin_client
    _set_current_admin_role(session, client, "ops")
    req = _create_request(session)

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(f"/admin/requests/{req.id}/archive", follow_redirects=False)
    assert resp.status_code == 403

    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="security.denied_action")
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.target_type == "Request"
    assert event.target_id == req.id
    payload = event.payload or {}
    assert payload.get("attempted_action") == "admin.admin_request_archive"
    assert payload.get("actor_role") == "ops"
    assert payload.get("required_roles") == ["superadmin"]
    assert payload.get("method") == "POST"


def test_get_403_not_logged(authenticated_admin_client, session):
    client = authenticated_admin_client
    _set_current_admin_role(session, client, "ops")

    session.query(AdminAuditEvent).delete()
    session.commit()

    before = session.query(AdminAuditEvent).filter_by(action="security.denied_action").count()
    resp = client.get("/admin/roles", follow_redirects=False)
    assert resp.status_code == 403
    after = session.query(AdminAuditEvent).filter_by(action="security.denied_action").count()
    assert after == before

