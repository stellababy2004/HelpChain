import re
from uuid import uuid4

import pytest

from backend.models import AdminAuditEvent, SocialRequest, SocialRequestEvent, User
from tests.test_master_e2e_operational import _admin, _real_admin_login

pytestmark = pytest.mark.mixed_transition


@pytest.fixture
def admin_login(app, db_session, init_test_data):
    structure = init_test_data["structure"]
    admin = _admin(
        db_session,
        username=f"full-flow-admin-{uuid4().hex[:8]}",
        role="superadmin",
        structure_id=None,
    )
    db_session.commit()
    client = app.test_client()
    _real_admin_login(client, admin)
    return client


def test_full_social_request_flow_html(
    client, admin_login, init_test_data, db_session
):
    structure = init_test_data["structure"]

    r = client.get("/requests/new")
    assert r.status_code == 200

    create_resp = client.post(
        "/requests/new",
        data={
            "structure_id": str(structure.id),
            "need_type": "urgence_sociale",
            "urgency": "high",
            "person_ref": "Dossier #FLOW-1",
            "description": "Signalement urgent pour une personne isolée.",
        },
        follow_redirects=False,
    )
    assert create_resp.status_code in (302, 303)
    location = create_resp.headers.get("Location", "")
    assert "/requests/" in location

    match = re.search(r"/requests/(\d+)", location)
    assert match is not None
    req_id = int(match.group(1))

    r_list = admin_login.get("/requests")
    assert r_list.status_code == 200
    list_html = r_list.get_data(as_text=True)
    assert "urgence_sociale" in list_html
    assert f"#{req_id}" in list_html

    assignee = db_session.query(User).filter_by(email="flow.assign@test.local").first()
    if not assignee:
        assignee = User(
            username="flow_assign_user",
            email="flow.assign@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        db_session.add(assignee)
        db_session.commit()

    assign_resp = admin_login.post(
        f"/requests/{req_id}/assign",
        data={"assigned_to_user_id": str(assignee.id)},
        follow_redirects=False,
    )
    assert assign_resp.status_code in (302, 303)

    assigned_events = SocialRequestEvent.query.filter_by(
        request_id=req_id, event_type="assigned"
    ).all()
    assert len(assigned_events) == 1

    status_resp = admin_login.post(
        f"/requests/{req_id}/status",
        data={"status": "resolved"},
        follow_redirects=False,
    )
    assert status_resp.status_code in (302, 303)

    sr = SocialRequest.query.get(req_id)
    assert sr is not None
    assert sr.status == "resolved"

    status_events = SocialRequestEvent.query.filter_by(
        request_id=req_id, event_type="status_changed"
    ).all()
    assert len(status_events) >= 1

    audit_event = (
        db_session.query(AdminAuditEvent)
        .filter(
            AdminAuditEvent.action == "social_request.status_changed",
            AdminAuditEvent.target_type == "Request",
            AdminAuditEvent.target_id == req_id,
        )
        .order_by(AdminAuditEvent.id.desc())
        .first()
    )
    assert audit_event is not None


def test_request_visible_in_admin_after_creation(
    admin_login, init_test_data, db_session
):
    structure = init_test_data["structure"]

    create_resp = admin_login.post(
        "/admin/requests/new",
        data={
            "title": "Request Flow Admin",
            "description": "Besoin d'aide alimentaire urgent.",
            "person_name": "Mme Dupont",
            "email": "mme.dupont@example.com",
            "phone": "+33123456789",
            "city": "Paris",
            "category": "food",
            "priority": "standard",
            "structure_id": str(structure.id),
        },
        follow_redirects=False,
    )
    assert create_resp.status_code in (302, 303)

    admin_list = admin_login.get("/admin/requests")
    assert admin_list.status_code == 200
    html = admin_list.get_data(as_text=True)
    assert "Request Flow Admin" in html
    assert "Aide alimentaire" in html
