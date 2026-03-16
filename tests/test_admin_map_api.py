from datetime import datetime, timezone

from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, Case, Request, Structure, User


def _login_admin_session(client, admin_id: int):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = admin_id


def test_admin_cases_map_api_returns_json(client, app):
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    with app.app_context():
        structure = Structure.query.filter_by(slug="default").first()
        if not structure:
            structure = Structure(name="Default", slug="default")
            db.session.add(structure)
            db.session.flush()

        admin = AdminUser(
            username="map_admin",
            email="map_admin@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        requester = User(
            username="map_req_user",
            email="map_req_user@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        db.session.add_all([admin, requester])
        db.session.flush()

        req = Request(
            title="map req",
            category="general",
            status="open",
            user_id=requester.id,
            structure_id=structure.id,
            created_at=now,
        )
        db.session.add(req)
        db.session.flush()

        case = Case(
            request_id=req.id,
            structure_id=structure.id,
            status="open",
            created_at=now,
        )
        db.session.add(case)
        db.session.commit()
        admin_id = admin.id

    _login_admin_session(client, admin_id)
    resp = client.get("/admin/api/cases/map")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "cases" in data
    assert isinstance(data["cases"], list)
    if data["cases"]:
        row = data["cases"][0]
        assert "id" in row
        assert "lat" in row
        assert "lng" in row
        assert "status" in row
        assert "risk_level" in row
        assert "created_at" in row
