from datetime import datetime, timedelta

from backend.extensions import db
from backend.helpchain_backend.src.models import (
    AdminUser,
    Request,
    RequestActivity,
    User,
    Volunteer,
    VolunteerRequestState,
)


def _login_admin_session(client, admin_id: int):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = admin_id


def test_admin_risk_kpis_includes_sla_aggregates(client, app):
    now = datetime.utcnow().replace(microsecond=0)

    with app.app_context():
        admin = AdminUser(
            username="sla_admin",
            email="sla_admin@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        requester = User(
            username="sla_req_user",
            email="sla_req_user@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        volunteer = Volunteer(email="sla_vol@test.local")
        db.session.add_all([admin, requester, volunteer])
        db.session.flush()

        req = Request(
            title="sla req",
            status="open",
            category="general",
            user_id=requester.id,
            assigned_volunteer_id=volunteer.id,
            created_at=now - timedelta(hours=3),
        )
        db.session.add(req)
        db.session.flush()

        db.session.add(
            VolunteerRequestState(
                volunteer_id=volunteer.id,
                request_id=req.id,
                notified_at=now - timedelta(hours=2),
                seen_at=now - timedelta(hours=1),
            )
        )
        db.session.add(
            RequestActivity(
                request_id=req.id,
                volunteer_id=volunteer.id,
                action="volunteer_can_help",
                created_at=now - timedelta(minutes=30),
            )
        )
        db.session.commit()
        admin_id = admin.id

    _login_admin_session(client, admin_id)
    resp = client.get("/admin/api/risk-kpis")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["avg_first_seen_seconds"] == 3600.0
    assert data["avg_first_action_seconds"] == 5400.0
    assert data["sla_under_12h_percent"] == 100.0
    assert data["sla_hours"] == 12
    assert data["sla_samples"] == 1
    assert data["sla_scope"] == "all_notified"


def test_admin_risk_kpis_accepts_sla_query_override(client, app):
    now = datetime.utcnow().replace(microsecond=0)

    with app.app_context():
        admin = AdminUser(
            username="sla_admin_q",
            email="sla_admin_q@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        requester = User(
            username="sla_req_user_q",
            email="sla_req_user_q@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        volunteer = Volunteer(email="sla_vol_q@test.local")
        db.session.add_all([admin, requester, volunteer])
        db.session.flush()

        req = Request(
            title="sla req q",
            status="open",
            category="general",
            user_id=requester.id,
            assigned_volunteer_id=volunteer.id,
            created_at=now - timedelta(hours=3),
        )
        db.session.add(req)
        db.session.flush()
        db.session.add(
            VolunteerRequestState(
                volunteer_id=volunteer.id,
                request_id=req.id,
                notified_at=now - timedelta(hours=2),
                seen_at=now - timedelta(hours=1),
            )
        )
        db.session.add(
            RequestActivity(
                request_id=req.id,
                volunteer_id=volunteer.id,
                action="volunteer_can_help",
                created_at=now - timedelta(minutes=30),
            )
        )
        db.session.commit()
        admin_id = admin.id

    _login_admin_session(client, admin_id)
    resp = client.get("/admin/api/risk-kpis?sla=6")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["sla_hours"] == 6


def test_admin_risk_kpis_sla_param_is_clamped(client, app):
    now = datetime.utcnow().replace(microsecond=0)

    with app.app_context():
        admin = AdminUser(
            username="sla_admin_clamp",
            email="sla_admin_clamp@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        requester = User(
            username="sla_req_user_clamp",
            email="sla_req_user_clamp@test.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        volunteer = Volunteer(email="sla_vol_clamp@test.local")
        db.session.add_all([admin, requester, volunteer])
        db.session.flush()

        req = Request(
            title="sla req clamp",
            status="open",
            category="general",
            user_id=requester.id,
            assigned_volunteer_id=volunteer.id,
            created_at=now - timedelta(hours=3),
        )
        db.session.add(req)
        db.session.flush()
        db.session.add(
            VolunteerRequestState(
                volunteer_id=volunteer.id,
                request_id=req.id,
                notified_at=now - timedelta(hours=2),
                seen_at=now - timedelta(hours=1),
            )
        )
        db.session.add(
            RequestActivity(
                request_id=req.id,
                volunteer_id=volunteer.id,
                action="volunteer_can_help",
                created_at=now - timedelta(minutes=30),
            )
        )
        db.session.commit()
        admin_id = admin.id

    _login_admin_session(client, admin_id)

    r_low = client.get("/admin/api/risk-kpis?sla=0")
    assert r_low.status_code == 200
    assert r_low.get_json()["sla_hours"] == 1

    r_high = client.get("/admin/api/risk-kpis?sla=100000")
    assert r_high.status_code == 200
    assert r_high.get_json()["sla_hours"] == 168
