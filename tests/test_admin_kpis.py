from datetime import datetime, timedelta, timezone

from backend.extensions import db
from backend.helpchain_backend.src.models import (
    AdminUser,
    Case,
    CaseEvent,
    Request,
    Structure,
    User,
)


def _login_admin_session(client, admin_id: int):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = admin_id


def test_admin_territorial_kpis_basic(client, app):
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    with app.app_context():
        structure = Structure.query.filter_by(slug="default").first()
        if not structure:
            structure = Structure(name="Default", slug="default")
            db.session.add(structure)
            db.session.flush()

        admin = AdminUser(
            username="kpi_admin",
            email="kpi_admin@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        requester = User(
            username="kpi_req_user",
            email="kpi_req_user@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        db.session.add_all([admin, requester])
        db.session.flush()

        req1 = Request(
            title="kpi req 1",
            category="general",
            status="open",
            user_id=requester.id,
            structure_id=structure.id,
            created_at=now - timedelta(hours=10),
        )
        req2 = Request(
            title="kpi req 2",
            category="general",
            status="open",
            user_id=requester.id,
            structure_id=structure.id,
            created_at=now - timedelta(hours=30),
        )
        req3 = Request(
            title="kpi req 3",
            category="general",
            status="closed",
            user_id=requester.id,
            structure_id=structure.id,
            created_at=now - timedelta(days=2),
        )
        db.session.add_all([req1, req2, req3])
        db.session.flush()

        case1 = Case(
            request_id=req1.id,
            structure_id=structure.id,
            status="new",
            created_at=req1.created_at,
        )
        case2 = Case(
            request_id=req2.id,
            structure_id=structure.id,
            status="in_progress",
            created_at=req2.created_at,
        )
        case3 = Case(
            request_id=req3.id,
            structure_id=structure.id,
            status="closed",
            created_at=req3.created_at,
        )
        db.session.add_all([case1, case2, case3])
        db.session.flush()

        db.session.add(
            CaseEvent(
                case_id=case1.id,
                event_type="note",
                created_at=now - timedelta(hours=8),
            )
        )
        db.session.add(
            CaseEvent(
                case_id=case2.id,
                event_type="note",
                created_at=now - timedelta(hours=20),
            )
        )
        db.session.commit()
        admin_id = admin.id

    _login_admin_session(client, admin_id)
    resp = client.get("/admin/api/territorial-kpis")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["active_cases"] == 2
    assert data["new_cases_week"] == 3
    assert data["resolved_cases"] == 1
    assert data["avg_response_hours"] == 6.0
    assert data["cases_by_status"] == {
        "new": 1,
        "in_progress": 1,
        "closed": 1,
    }
    assert data["oldest_open_case_days"] == 1
