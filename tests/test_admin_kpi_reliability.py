from datetime import UTC, datetime, timedelta

from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, Request, Structure, User


def _login_admin(client, admin_id: int) -> None:
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
        sess["admin_user_id"] = admin_id
        sess["admin_logged_in"] = True
        sess["mfa_ok"] = True


def _make_structure(slug: str) -> Structure:
    structure = Structure(name=slug.replace("-", " ").title(), slug=slug)
    db.session.add(structure)
    db.session.flush()
    return structure


def _make_request(
    *,
    title: str,
    user_id: int,
    structure_id: int,
    status: str | None,
    created_at: datetime,
    completed_at: datetime | None = None,
    owned_at: datetime | None = None,
    is_archived: bool = False,
    deleted_at: datetime | None = None,
) -> Request:
    row = Request(
        title=title,
        category="general",
        user_id=user_id,
        structure_id=structure_id,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        owned_at=owned_at,
        is_archived=is_archived,
        deleted_at=deleted_at,
    )
    db.session.add(row)
    return row


def _seed_admin_scope(slug_prefix: str):
    structure = _make_structure(f"{slug_prefix}-scope")
    other_structure = _make_structure(f"{slug_prefix}-other")
    admin = AdminUser(
        username=f"{slug_prefix}_admin",
        email=f"{slug_prefix}_admin@test.local",
        password_hash="x",
        role="admin",
        structure_id=structure.id,
        is_active=True,
    )
    user = User(
        username=f"{slug_prefix}_requester",
        email=f"{slug_prefix}_requester@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    db.session.add_all([admin, user])
    db.session.flush()
    return structure.id, other_structure.id, admin.id, user.id


def test_ops_kpis_exclude_archived_deleted_and_other_structures(client, app, session):
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    with app.app_context():
        structure_id, other_structure_id, admin_id, user_id = _seed_admin_scope(
            "ops-kpi"
        )
        _make_request(
            title="visible-open",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now - timedelta(days=1),
        )
        _make_request(
            title="visible-stale",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now - timedelta(days=8),
        )
        _make_request(
            title="visible-resolved",
            user_id=user_id,
            structure_id=structure_id,
            status="done",
            created_at=now - timedelta(hours=5),
            completed_at=now - timedelta(hours=1),
            owned_at=now - timedelta(hours=4),
        )
        _make_request(
            title="archived-hidden",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now,
            is_archived=True,
        )
        _make_request(
            title="deleted-hidden",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now,
            deleted_at=now,
        )
        _make_request(
            title="other-structure-hidden",
            user_id=user_id,
            structure_id=other_structure_id,
            status="open",
            created_at=now,
        )
        db.session.commit()

    _login_admin(client, admin_id)
    response = client.get("/admin/api/ops-kpis?days=30")

    assert response.status_code == 200
    data = response.get_json()
    assert data["new_requests"] == 3
    assert data["resolved_requests"] == 1
    assert data["stale_over_7d"] == 1
    assert data["by_status_open"] == [{"status": "open", "count": 2}]
    assert data["definition"]["scope"] == (
        "current structure, excluding archived and deleted requests"
    )


def test_admin_dashboard_api_uses_same_request_visibility_scope(client, app, session):
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    with app.app_context():
        structure_id, other_structure_id, admin_id, user_id = _seed_admin_scope(
            "dashboard-kpi"
        )
        _make_request(
            title="dashboard-visible-open",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now,
        )
        _make_request(
            title="dashboard-visible-done",
            user_id=user_id,
            structure_id=structure_id,
            status="done",
            created_at=now,
            completed_at=now,
        )
        _make_request(
            title="dashboard-archived-hidden",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now,
            is_archived=True,
        )
        _make_request(
            title="dashboard-deleted-hidden",
            user_id=user_id,
            structure_id=structure_id,
            status="open",
            created_at=now,
            deleted_at=now,
        )
        _make_request(
            title="dashboard-other-structure-hidden",
            user_id=user_id,
            structure_id=other_structure_id,
            status="open",
            created_at=now,
        )
        db.session.commit()

    _login_admin(client, admin_id)
    response = client.get("/admin/api/dashboard?days=30")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total_requests"] == 2
    assert data["counts_by_status"] == {"done": 1, "open": 1}
    assert data["timeseries"] == [{"date": now.date().isoformat(), "count": 2}]
