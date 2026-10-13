from datetime import UTC, datetime
from uuid import uuid4

from backend.models import AdminUser, Structure
from backend.helpchain_backend.src.models import CalendarEvent, Case, Request


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


def _make_request(session, *, structure_id, owner_id=None, title="Calendar request"):
    request_row = Request(
        title=title,
        description="Calendar follow-up request",
        category="general",
        status="open",
        structure_id=structure_id,
        owner_id=owner_id,
    )
    session.add(request_row)
    session.commit()
    return request_row


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


def test_request_detail_can_plan_follow_up_in_organization_calendar(client, session):
    structure = _make_structure(
        session,
        structure_id=9206,
        name="Calendar Follow-up",
        slug="calendar-follow-up",
    )
    admin = _make_admin(session, structure_id=structure.id)
    request_row = _make_request(
        session,
        structure_id=structure.id,
        owner_id=admin.id,
        title="Housing follow-up",
    )
    case = Case(
        request_id=request_row.id,
        structure_id=structure.id,
        status="new",
        priority="normal",
    )
    session.add(case)
    session.commit()

    _login_admin(client, admin)

    detail_response = client.get(f"/admin/requests/{request_row.id}")
    assert detail_response.status_code == 200
    detail_html = detail_response.get_data(as_text=True)
    assert "Planifier une relance" in detail_html
    assert f'/admin/calendar?request_id={request_row.id}' in detail_html

    calendar_response = client.get(
        f"/admin/calendar?request_id={request_row.id}"
    )
    assert calendar_response.status_code == 200
    calendar_html = calendar_response.get_data(as_text=True)
    assert 'class="collapse show mb-3" id="calendar-new-event"' in calendar_html
    assert 'name="request_id" value="{}"'.format(request_row.id) in calendar_html
    assert 'value="follow_up" selected' in calendar_html

    create_response = client.post(
        "/admin/calendar/events",
        data={
            "request_id": str(request_row.id),
            "title": "Relance logement",
            "event_type": "follow_up",
            "starts_at": "2026-10-25T09:30",
            "ends_at": "",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    event = CalendarEvent.query.filter_by(title="Relance logement").one()
    assert event.event_type == "follow_up"
    assert event.structure_id == structure.id
    assert event.request_id == request_row.id
    assert event.case_id == case.id


def test_request_follow_up_calendar_rejects_cross_structure_request(client, session):
    own_structure = _make_structure(
        session,
        structure_id=9207,
        name="Calendar Link Own",
        slug="calendar-link-own",
    )
    other_structure = _make_structure(
        session,
        structure_id=9208,
        name="Calendar Link Other",
        slug="calendar-link-other",
    )
    admin = _make_admin(session, structure_id=own_structure.id)
    other_request = _make_request(
        session,
        structure_id=other_structure.id,
        title="Other tenant request",
    )

    _login_admin(client, admin)

    assert client.get(
        f"/admin/calendar?request_id={other_request.id}"
    ).status_code == 404

    before = CalendarEvent.query.count()
    response = client.post(
        "/admin/calendar/events",
        data={
            "request_id": str(other_request.id),
            "title": "Forbidden follow-up",
            "event_type": "follow_up",
            "starts_at": "2026-10-25T10:30",
        },
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert CalendarEvent.query.count() == before


def test_calendar_event_modal_links_to_request_and_case(client, session):
    structure = _make_structure(
        session,
        structure_id=9209,
        name="Calendar Linked Records",
        slug="calendar-linked-records",
    )
    admin = _make_admin(session, structure_id=structure.id)
    request_row = _make_request(session, structure_id=structure.id)
    case = Case(
        request_id=request_row.id,
        structure_id=structure.id,
        status="new",
        priority="normal",
    )
    event = CalendarEvent(
        structure_id=structure.id,
        request_id=request_row.id,
        case=case,
        title="Linked follow-up",
        event_type="follow_up",
        status="scheduled",
        starts_at=datetime(2026, 10, 26, 10, 0, tzinfo=UTC),
        all_day=False,
    )
    session.add_all([case, event])
    session.commit()

    _login_admin(client, admin)

    response = client.get("/admin/calendar")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Voir la demande" in html
    assert f'href="/admin/requests/{request_row.id}"' in html
    assert "Ouvrir le dossier" in html
    assert f'href="/admin/cases/{case.id}"' in html




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
