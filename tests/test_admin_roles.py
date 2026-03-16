from uuid import uuid4

from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest
from backend.models import AdminUser, Request, Structure, User, Volunteer


def _admin_id_from_client(client) -> int:
    with client.session_transaction() as sess:
        val = (
            sess.get("admin_user_id")
            or sess.get("admin_id")
            or sess.get("user_id")
            or sess.get("_user_id")
        )
    return int(val)


def _set_admin_role(session, client, role: str) -> None:
    admin_id = _admin_id_from_client(client)
    admin = session.get(AdminUser, admin_id)
    admin.role = role
    session.commit()


def _create_request(session) -> Request:
    structure = session.query(Structure).filter_by(slug="default").first()
    suffix = uuid4().hex[:8]
    user = User(
        username=f"role_req_user_{suffix}",
        email=f"role_req_{suffix}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()

    req = Request(
        title=f"Role request {suffix}",
        user_id=user.id,
        status="pending",
        category="general",
        structure_id=getattr(structure, "id", None),
    )
    session.add(req)
    session.commit()
    return req


def _create_interest(session, req_id: int) -> VolunteerInterest:
    suffix = uuid4().hex[:8]
    volunteer = Volunteer(
        name=f"Role Volunteer {suffix}",
        email=f"role_vol_{suffix}@test.local",
        is_active=True,
    )
    session.add(volunteer)
    session.flush()

    interest = VolunteerInterest(
        volunteer_id=volunteer.id,
        request_id=req_id,
        status="pending",
    )
    session.add(interest)
    session.commit()
    return interest


def test_readonly_can_view_security_but_cannot_archive_or_unlock(
    authenticated_admin_client, session
):
    client = authenticated_admin_client
    _set_admin_role(session, client, "readonly")
    req = _create_request(session)

    view_resp = client.get("/admin/security", follow_redirects=False)
    assert view_resp.status_code == 403

    archive_resp = client.post(
        f"/admin/requests/{req.id}/archive", follow_redirects=False
    )
    assert archive_resp.status_code == 403

    unlock_resp = client.post(f"/admin/requests/{req.id}/unlock", follow_redirects=False)
    assert unlock_resp.status_code == 403


def test_ops_can_approve_interest_but_cannot_archive_or_unlock(
    authenticated_admin_client, session
):
    client = authenticated_admin_client
    _set_admin_role(session, client, "ops")
    req = _create_request(session)
    interest = _create_interest(session, req.id)

    approve_resp = client.post(
        f"/admin/requests/{req.id}/interests/{interest.id}/approve",
        follow_redirects=False,
    )
    assert approve_resp.status_code in (302, 303)

    archive_resp = client.post(
        f"/admin/requests/{req.id}/archive", follow_redirects=False
    )
    assert archive_resp.status_code == 403

    unlock_resp = client.post(f"/admin/requests/{req.id}/unlock", follow_redirects=False)
    assert unlock_resp.status_code == 403


def test_superadmin_can_archive_and_unlock(authenticated_admin_client, session):
    client = authenticated_admin_client
    _set_admin_role(session, client, "superadmin")
    req = _create_request(session)

    archive_resp = client.post(
        f"/admin/requests/{req.id}/archive", follow_redirects=False
    )
    assert archive_resp.status_code in (302, 303)

    unlock_resp = client.post(f"/admin/requests/{req.id}/unlock", follow_redirects=False)
    assert unlock_resp.status_code in (302, 303)
