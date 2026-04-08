from datetime import timedelta

from backend.models import AdminAuditEvent, AdminLoginAttempt, AdminUser, utc_now


def test_admin_security_page_renders_with_data(authenticated_admin_client, session):
    client = authenticated_admin_client
    now = utc_now()
    admin_id = None
    with client.session_transaction() as sess:
        admin_id = int(
            sess.get("admin_user_id")
            or sess.get("admin_id")
            or sess.get("user_id")
            or sess.get("_user_id")
        )
    admin = session.get(AdminUser, admin_id)
    admin.role = "superadmin"
    admin.structure_id = None
    admin.mfa_enabled = True
    admin.totp_secret = "test-mfa-secret"
    session.commit()
    with client.session_transaction() as sess:
        sess["role"] = "superadmin"
        sess["mfa_required"] = True
        sess[client.application.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
        sess["mfa_ok_until"] = (utc_now() + timedelta(minutes=30)).isoformat()

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
    assert "Denied actions (24h)" in html
    assert "interest.reject" in html
    assert "10.0.0.2" in html
    assert "Spike:" in html
    assert ("Repeated IP:" in html) or ("Repeated fails by IP" in html) or ("Top denied IP:" in html)
    assert ("Repeated username:" in html) or ("Repeated fails by username" in html) or ("Top denied username:" in html)
