from datetime import UTC, datetime
from uuid import uuid4

from backend.models import AdminUser, Structure
from backend.helpchain_backend.src.models import CalendarEvent


def _login_admin(client, admin_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["user_id"] = admin_user.id
        sess["admin_id"] = admin_user.id
        sess["admin_user_id"] = admin_user.id
        sess["role"] = admin_user.role
        sess["is_authenticated"] = True
        sess["is_admin"] = True
        sess["admin_logged_in"] = True


def _make_structure(session, *, structure_id, name, slug):
    structure = session.get(Structure, structure_id)
    if structure is None:
        structure = Structure(id=structure_id, name=name, slug=slug)
        session.add(structure)
        session.commit()
    return structure


def _make_admin(session, *, structure_id):
    suffix = uuid4().hex[:8]
    admin = AdminUser(
        username=f"calendar_admin_{suffix}",
        email=f"calendar_admin_{suffix}@test.local",
        password_hash="x",
        role="admin",
        is_active=True,
        structure_id=structure_id,
    )
    session.add(admin)
    session.commit()
    return admin


def test_calendar_is_structure_scoped(client, session):
    own_structure = _make_structure(
        session,
        structure_id=9201,
        name="Calendar Own",
        slug="calendar-own",
    )
    other_structure = _make_structure(
        session,
        structure_id=9202,
        name="Calendar Other",
        slug="calendar-other",
    )

    admin = _make_admin(session, structure_id=own_structure.id)

    own_event = CalendarEvent(
        structure_id=own_structure.id,
        title="Visible calendar event",
        event_type="meeting",
        status="scheduled",
        starts_at=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
        all_day=False,
    )
    other_event = CalendarEvent(
        structure_id=other_structure.id,
        title="Hidden calendar event",
        event_type="meeting",
        status="scheduled",
        starts_at=datetime(2026, 10, 20, 11, 0, tzinfo=UTC),
        all_day=False,
    )

    session.add_all([own_event, other_event])
    session.commit()

    own_id = own_event.id
    other_id = other_event.id

    _login_admin(client, admin)

    response = client.get("/admin/calendar", follow_redirects=False)

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Visible calendar event" in html
    assert "Hidden calendar event" not in html

def test_calendar_create_event_uses_admin_structure(client, session):
    structure = _make_structure(
        session,
        structure_id=9203,
        name="Calendar Create",
        slug="calendar-create",
    )
    admin = _make_admin(session, structure_id=structure.id)
    admin_id = admin.id

    _login_admin(client, admin)

    response = client.post(
        "/admin/calendar/events",
        data={
            "title": "Reunion parents",
            "description": "Point de suivi",
            "event_type": "meeting",
            "starts_at": "2026-10-21T14:00",
            "ends_at": "2026-10-21T15:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/admin/calendar")

    event = CalendarEvent.query.filter_by(
        title="Reunion parents"
    ).one()

    assert event.structure_id == structure.id
    assert event.created_by_user_id == admin_id
    assert event.event_type == "meeting"
    assert event.status == "scheduled"

def test_global_admin_cannot_create_event_without_explicit_structure(client, session):
    suffix = uuid4().hex[:8]
    admin = AdminUser(
        username=f"calendar_global_{suffix}",
        email=f"calendar_global_{suffix}@test.local",
        password_hash="x",
        role="superadmin",
        is_active=True,
        structure_id=None,
    )
    session.add(admin)
    session.commit()

    _login_admin(client, admin)

    before = CalendarEvent.query.count()

    response = client.post(
        "/admin/calendar/events",
        data={
            "title": "Must not use default tenant",
            "event_type": "meeting",
            "starts_at": "2026-10-22T10:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/admin/calendar")
    assert CalendarEvent.query.count() == before




def test_calendar_update_and_delete_are_structure_scoped(client, session):
    own_structure = _make_structure(
        session,
        structure_id=9204,
        name="Calendar Edit Own",
        slug="calendar-edit-own",
    )
    other_structure = _make_structure(
        session,
        structure_id=9205,
        name="Calendar Edit Other",
        slug="calendar-edit-other",
    )
    admin = _make_admin(session, structure_id=own_structure.id)

    own_event = CalendarEvent(
        structure_id=own_structure.id,
        title="Own event",
        event_type="meeting",
        status="scheduled",
        starts_at=datetime(2026, 10, 23, 10, 0, tzinfo=UTC),
        all_day=False,
    )
    other_event = CalendarEvent(
        structure_id=other_structure.id,
        title="Other event",
        event_type="meeting",
        status="scheduled",
        starts_at=datetime(2026, 10, 23, 11, 0, tzinfo=UTC),
        all_day=False,
    )
    session.add_all([own_event, other_event])
    session.commit()

    own_id = own_event.id
    other_id = other_event.id

    _login_admin(client, admin)

    response = client.post(
        f"/admin/calendar/events/{own_id}/update",
        data={
            "title": "Own event updated",
            "event_type": "follow_up",
            "starts_at": "2026-10-24T12:00",
            "ends_at": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    session.expire_all()
    assert session.get(CalendarEvent, own_id).title == "Own event updated"

    response = client.post(
        f"/admin/calendar/events/{other_id}/update",
        data={
            "title": "Hacked",
            "event_type": "meeting",
            "starts_at": "2026-10-24T12:00",
            "ends_at": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 404
    session.expire_all()
    assert session.get(CalendarEvent, other_id).title == "Other event"

    response = client.post(
        f"/admin/calendar/events/{other_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 404
    assert session.get(CalendarEvent, other_id) is not None

    response = client.post(
        f"/admin/calendar/events/{own_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    session.expire_all()
    assert session.get(CalendarEvent, own_id) is None
