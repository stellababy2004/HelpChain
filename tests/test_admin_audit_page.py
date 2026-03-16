from backend.models import AdminAuditEvent


def test_admin_audit_page_renders_events(authenticated_admin_client, session):
    client = authenticated_admin_client

    session.query(AdminAuditEvent).delete()
    session.add(
        AdminAuditEvent(
            admin_user_id=1,
            admin_username="admin",
            action="STATUS_CHANGE",
            target_type="Request",
            target_id=123,
            ip="127.0.0.1",
            payload={"old": {"status": "open"}, "new": {"status": "in_progress"}},
        )
    )
    session.commit()

    resp = client.get("/admin/audit", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "STATUS_CHANGE" in html
    assert "Request #123" in html


def test_admin_audit_page_filter_by_action(authenticated_admin_client, session):
    client = authenticated_admin_client

    session.query(AdminAuditEvent).delete()
    session.add(
        AdminAuditEvent(
            admin_user_id=1,
            admin_username="admin",
            action="STATUS_CHANGE",
            target_type="Request",
            target_id=1,
        )
    )
    session.add(
        AdminAuditEvent(
            admin_user_id=1,
            admin_username="admin",
            action="request.archive",
            target_type="Request",
            target_id=2,
        )
    )
    session.commit()

    resp = client.get("/admin/audit?action=request.archive", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "request.archive" in html
