from datetime import timedelta

from backend.models import AdminAuditEvent, utc_now


def _seed_denied(session, *, ip: str, username: str, minutes_ago: int):
    session.add(
        AdminAuditEvent(
            admin_user_id=1,
            admin_username=username,
            action="security.denied_action",
            target_type="Request",
            target_id=101,
            ip=ip,
            payload={
                "attempted_action": "admin.admin_request_archive",
                "required_roles": ["superadmin"],
                "actor_role": "ops",
                "method": "POST",
                "path": "/admin/requests/101/archive",
            },
            created_at=utc_now() - timedelta(minutes=minutes_ago),
        )
    )


def test_security_shows_denied_tables(authenticated_admin_client, session):
    client = authenticated_admin_client
    session.query(AdminAuditEvent).filter(
        AdminAuditEvent.action == "security.denied_action"
    ).delete(synchronize_session=False)
    session.commit()

    _seed_denied(session, ip="10.10.10.1", username="ops", minutes_ago=10)
    _seed_denied(session, ip="10.10.10.1", username="ops", minutes_ago=20)
    _seed_denied(session, ip="10.10.10.2", username="readonly", minutes_ago=30)
    session.commit()

    resp = client.get("/admin/security", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Top denied-action IPs (24h)" in html
    assert "Top denied-action usernames (24h)" in html
    assert "10.10.10.1" in html
    assert "readonly" in html


def test_security_denied_badges_on(authenticated_admin_client, session):
    client = authenticated_admin_client
    session.query(AdminAuditEvent).filter(
        AdminAuditEvent.action == "security.denied_action"
    ).delete(synchronize_session=False)
    session.commit()

    # denied_1h = 6 -> spike ON (threshold max(5, 3*avg))
    for _ in range(6):
        _seed_denied(session, ip="55.55.55.55", username="ops", minutes_ago=15)
    # top denied IP count >= 10 -> repeated denied ON
    for _ in range(4):
        _seed_denied(session, ip="55.55.55.55", username="ops", minutes_ago=120)
    session.commit()

    resp = client.get("/admin/security", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Denied spike: ON" in html
    assert "Repeated denied: ON" in html

