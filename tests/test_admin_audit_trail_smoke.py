import os

from backend.models import AdminAuditEvent, AdminUser

TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "TestPassword1")


def _ensure_admin_user(session, username: str, password: str) -> AdminUser:
    admin = session.query(AdminUser).filter_by(username=username).first()
    if not admin:
        admin = AdminUser(
            username=username,
            email=f"{username}@test.local",
            role="admin",
            is_active=True,
        )
        session.add(admin)
    admin.set_password(password)
    session.commit()
    return admin


def test_admin_login_success_writes_audit_event(client, session):
    client.application.config["EMAIL_2FA_ENABLED"] = False
    admin = _ensure_admin_user(session, "audit_login_admin", TEST_ADMIN_PASSWORD)
    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.post(
        "/admin/login",
        data={"username": admin.username, "password": TEST_ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    event = (
        session.query(AdminAuditEvent)
        .filter(
            AdminAuditEvent.action == "admin.login.success",
            AdminAuditEvent.target_type == "AdminUser",
            AdminAuditEvent.target_id == int(admin.id),
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
    assert (event.payload or {}).get("via") in {
        "admin_login_legacy",
        "admin_ops_login",
    }


def test_admin_logout_writes_audit_event(authenticated_admin_client, session):
    client = authenticated_admin_client
    with client.session_transaction() as sess:
        admin_id = int(sess.get("admin_user_id") or sess.get("admin_id") or 0)

    session.query(AdminAuditEvent).delete()
    session.commit()

    resp = client.get("/admin/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)

    event = (
        session.query(AdminAuditEvent)
        .filter(
            AdminAuditEvent.action == "admin.logout",
            AdminAuditEvent.target_type == "AdminUser",
            AdminAuditEvent.target_id == admin_id,
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert event is not None
