import re
import time
from datetime import datetime
from uuid import uuid4

import pytest

from backend.models import AdminUser, Request, RequestActivity, Structure, User

pytestmark = pytest.mark.spine


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


@pytest.fixture
def admin_login(authenticated_admin_client, session):
    _set_admin_role(session, authenticated_admin_client, "ops")
    return authenticated_admin_client


@pytest.fixture
def make_request(session, admin_login):
    admin_id = _admin_id_from_client(admin_login)

    def _make_request(status: str = "pending") -> Request:
        structure = session.query(Structure).filter_by(slug="default").first()
        suffix = uuid4().hex[:8]
        user = User(
            username=f"bulk_req_user_{suffix}",
            email=f"bulk_req_{suffix}@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        session.add(user)
        session.flush()

        req = Request(
            title=f"Bulk request {suffix}",
            user_id=user.id,
            status=status,
            category="general",
            structure_id=getattr(structure, "id", None),
            owner_id=admin_id,
        )
        session.add(req)
        session.commit()
        return req

    return _make_request


def test_status_cannot_move_back_to_open(admin_login, db_session, make_request):
    req1 = make_request(status="in_progress")
    req2 = make_request(status="in_progress")

    for req in (req1, req2):
        r = admin_login.post(
            f"/admin/requests/{req.id}/status",
            data={"status": "pending"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 303)

    db_session.refresh(req1)
    db_session.refresh(req2)
    assert req1.status == "in_progress"
    assert req2.status == "in_progress"


def test_status_can_complete_in_progress(admin_login, db_session, make_request):
    req = make_request(status="in_progress")

    r = admin_login.post(
        f"/admin/requests/{req.id}/status",
        data={"status": "done"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    db_session.refresh(req)
    assert req.status == "done"
    assert req.completed_at is not None


@pytest.mark.parametrize("endpoint", ["update_status", "requests"])
@pytest.mark.parametrize("old_status", ["open", "in_progress", "done", "cancelled"])
@pytest.mark.parametrize("target_status", ["open", "in_progress", "done", "cancelled"])
def test_request_status_transition_matrix(
    admin_login, db_session, make_request, endpoint, old_status, target_status
):
    allowed = {
        ("open", "in_progress"),
        ("open", "cancelled"),
        ("in_progress", "done"),
        ("in_progress", "cancelled"),
    }
    req = make_request(status=old_status)
    if old_status in {"done", "cancelled"}:
        req.completed_at = datetime(2026, 1, 1, 12)
        db_session.commit()
    db_session.refresh(req)
    before_completed = req.completed_at
    before_updated = req.updated_at
    before_activities = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id)
        .count()
    )
    url = (
        f"/admin/update_status/{req.id}"
        if endpoint == "update_status"
        else f"/admin/requests/{req.id}/status"
    )
    response = admin_login.post(
        url,
        data={"status": target_status},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    db_session.refresh(req)
    after_activities = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id)
        .count()
    )
    if (old_status, target_status) in allowed:
        assert req.status == target_status
        assert after_activities > before_activities
        if target_status in {"done", "cancelled"}:
            assert req.completed_at is not None
    else:
        assert req.status == old_status
        assert req.completed_at == before_completed
        assert req.updated_at == before_updated
        assert after_activities == before_activities


@pytest.mark.parametrize(
    "old_status",
    ["completed", "resolved", "closed", "canceled", "rejected"],
)
def test_legacy_terminal_status_cannot_reopen(
    admin_login, db_session, make_request, old_status
):
    req = make_request(status=old_status)
    response = admin_login.post(
        f"/admin/requests/{req.id}/status",
        data={"status": "in_progress"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "invalid_status_transition"
    db_session.refresh(req)
    assert req.status == old_status


@pytest.mark.parametrize(
    "action, expected",
    [
        ("status:pending", ["open", "in_progress", "done", "cancelled"]),
        ("status:in_progress", ["in_progress", "in_progress", "done", "cancelled"]),
        ("status:done", ["open", "done", "done", "cancelled"]),
        ("status:rejected", ["cancelled", "cancelled", "done", "cancelled"]),
    ],
)
def test_bulk_respects_lifecycle_transitions(
    admin_login, db_session, make_request, action, expected
):
    rows = [
        make_request(status=status)
        for status in ["open", "in_progress", "done", "cancelled"]
    ]
    response = admin_login.post(
        "/admin/requests/bulk",
        data={
            "bulk_action": action,
            "selected_ids": [str(req.id) for req in rows],
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    for req, expected_status in zip(rows, expected):
        db_session.refresh(req)
        assert req.status == expected_status


@pytest.mark.parametrize(
    "old_status, expected_status",
    [
        ("open", "cancelled"),
        ("pending", "cancelled"),
        ("in_progress", "cancelled"),
        ("approved", "cancelled"),
        ("done", "done"),
        ("completed", "completed"),
        ("resolved", "resolved"),
        ("closed", "closed"),
        ("cancelled", "cancelled"),
        ("canceled", "canceled"),
        ("rejected", "rejected"),
    ],
)
def test_archive_preserves_lifecycle_and_is_idempotent(
    admin_login, db_session, make_request, old_status, expected_status
):
    _set_admin_role(db_session, admin_login, "superadmin")
    req = make_request(status=old_status)
    terminal = old_status in {
        "done", "completed", "resolved", "closed",
        "cancelled", "canceled", "rejected",
    }
    if terminal:
        req.completed_at = datetime(2026, 1, 1, 12)
        db_session.commit()
    db_session.refresh(req)
    before_completed = req.completed_at
    before_status_changes = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id, action="status_change")
        .count()
    )

    admin_id = _admin_id_from_client(admin_login)
    with admin_login.session_transaction() as sess:
        sess["admin_mfa_last_verified"] = int(time.time())
        sess["admin_mfa_user_id"] = admin_id

    url = f"/admin/requests/{req.id}/archive"
    response = admin_login.post(url, follow_redirects=False)
    assert response.status_code in (302, 303)
    db_session.refresh(req)
    assert req.status == expected_status
    assert req.is_archived is True
    assert req.archived_at is not None

    if terminal:
        assert req.completed_at == before_completed
    else:
        assert req.completed_at is not None

    after_status_changes = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id, action="status_change")
        .count()
    )
    assert after_status_changes == before_status_changes + int(not terminal)

    archive_events = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id, action="archive")
        .all()
    )
    assert len(archive_events) == 1
    assert archive_events[0].actor_admin_id == admin_id

    archived_at = req.archived_at
    completed_at = req.completed_at
    updated_at = req.updated_at
    activity_count = (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id)
        .count()
    )

    response = admin_login.post(url, follow_redirects=False)
    assert response.status_code in (302, 303)
    db_session.refresh(req)
    assert req.status == expected_status
    assert req.is_archived is True
    assert req.archived_at == archived_at
    assert req.completed_at == completed_at
    assert req.updated_at == updated_at
    assert (
        db_session.query(RequestActivity)
        .filter_by(request_id=req.id)
        .count()
    ) == activity_count


@pytest.mark.parametrize(
    "old_status, expected_choices",
    [
        ("open", {"open", "in_progress", "cancelled"}),
        ("pending", {"open", "in_progress", "cancelled"}),
        ("in_progress", {"in_progress", "done", "cancelled"}),
        ("approved", {"in_progress", "done", "cancelled"}),
        ("done", set()),
        ("completed", set()),
        ("resolved", set()),
        ("closed", set()),
        ("cancelled", set()),
        ("canceled", set()),
        ("rejected", set()),
    ],
)
def test_lifecycle_form_matches_allowed_transitions(
    admin_login, make_request, old_status, expected_choices
):
    req = make_request(status=old_status)
    response = admin_login.get(f"/admin/requests/{req.id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    panel = re.search(
        r"<!-- Status management -->(.*?)<!-- Ownership -->",
        html,
        re.S,
    )
    assert panel is not None
    select = re.search(
        r'<select\b[^>]*\bid="statusSelect"[^>]*>(.*?)</select>',
        panel.group(1),
        re.S,
    )
    if expected_choices:
        assert select is not None
        choices = re.findall(
            r'<option\b[^>]*\bvalue="([^"]+)"',
            select.group(1),
        )
        assert set(choices) == expected_choices
        assert len(choices) == len(expected_choices)
        assert "Modifiable" in panel.group(1)
    else:
        assert select is None
        assert 'id="statusForm"' not in panel.group(1)
        assert "Modifiable" not in panel.group(1)
        assert "Le statut ne peut plus être modifié." in panel.group(1)
