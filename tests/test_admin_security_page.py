from datetime import timedelta

from backend.models import AdminAuditEvent, AdminLoginAttempt, utc_now


def test_admin_security_page_renders_with_data(authenticated_admin_client, session):
    client = authenticated_admin_client
    now = utc_now()

    session.query(AdminLoginAttempt).delete()
    session.query(AdminAuditEvent).delete()

    session.add(
        AdminLoginAttempt(
            created_at=now - timedelta(hours=2),
            username="admin",
            ip="10.0.0.1",
            success=True,
        )
    )
    for _ in range(6):
        session.add(
            AdminLoginAttempt(
                created_at=now - timedelta(minutes=20),
                username="admin",
                ip="10.0.0.2",
                success=False,
            )
        )

    session.add(
        AdminAuditEvent(
            admin_user_id=1,
            admin_username="admin",
            action="interest.reject",
            target_type="Interest",
            target_id=77,
            ip="127.0.0.1",
            payload={"req_id": 12, "interest_id": 77},
        )
    )
    session.commit()

    resp = client.get("/admin/security", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Security overview" in html
    assert "Lockout buckets (24h)" in html
    assert "interest.reject" in html
    assert "10.0.0.2" in html
    assert "Spike:" in html
    assert "Repeated IP:" in html
    assert "Repeated username:" in html
