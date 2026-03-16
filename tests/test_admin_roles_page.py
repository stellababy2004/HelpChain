from uuid import uuid4

from backend.models import AdminAuditEvent, AdminUser


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


def _create_admin(session, role: str) -> AdminUser:
    suffix = uuid4().hex[:8]
    user = AdminUser(
        username=f"role_admin_{suffix}",
        email=f"role_admin_{suffix}@test.local",
        password_hash="x",
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def test_roles_page_superadmin_access(authenticated_admin_client, session):
    client = authenticated_admin_client
    _set_current_admin_role(session, client, "superadmin")
    resp = client.get("/admin/roles", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Admin roles" in html
    assert "Governance" in html


def test_roles_page_denied_for_ops(authenticated_admin_client, session):
    client = authenticated_admin_client
    _set_current_admin_role(session, client, "ops")
    resp = client.get("/admin/roles", follow_redirects=False)
    assert resp.status_code == 403


def test_change_role_logs_audit_event(authenticated_admin_client, session):
    client = authenticated_admin_client
    actor = _set_current_admin_role(session, client, "superadmin")
    target = _create_admin(session, "ops")

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        f"/admin/roles/{target.id}/role",
        data={"role": "readonly"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    updated = session.get(AdminUser, target.id)
    assert updated.role == "readonly"

    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="ROLE_CHANGE", target_type="AdminUser", target_id=target.id)
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    payload = event.payload or {}
    assert payload.get("old", {}).get("role") == "ops"
    assert payload.get("new", {}).get("role") == "readonly"
    assert payload.get("actor", {}).get("admin_user_id") == actor.id


def test_cannot_downgrade_last_superadmin(authenticated_admin_client, session):
    client = authenticated_admin_client
    actor = _set_current_admin_role(session, client, "superadmin")

    # Ensure no other superadmin remains.
    (
        session.query(AdminUser)
        .filter(AdminUser.id != actor.id)
        .update({"role": "ops"}, synchronize_session=False)
    )
    session.commit()

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        f"/admin/roles/{actor.id}/role",
        data={"role": "ops"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    refreshed = session.get(AdminUser, actor.id)
    assert refreshed.role in ("superadmin", "admin")

    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="ROLE_CHANGE", target_type="AdminUser", target_id=actor.id)
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is None

