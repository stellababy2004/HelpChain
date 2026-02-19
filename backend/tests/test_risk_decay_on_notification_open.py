from datetime import datetime, timedelta, timezone

from backend.helpchain_backend.src.models import (
    Notification,
    Request,
    User,
    Volunteer,
    VolunteerRequestState,
)
from backend.helpchain_backend.src.notifications.inapp import mark_notification_opened
from backend.helpchain_backend.src.routes.admin import build_requests_query


def test_risk_decays_after_notification_open(app, session):
    now = datetime.now(timezone.utc)

    req_user = User(
        username="risk_decay_user",
        email="risk_decay_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Risk Decay Volunteer",
        email="risk_decay_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    req = Request(
        title="seed risk decay request",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add(req)
    session.flush()

    state = VolunteerRequestState(
        request_id=req.id,
        volunteer_id=volunteer.id,
        notified_at=now - timedelta(hours=25),
        seen_at=None,
    )
    session.add(state)

    notif = Notification(
        volunteer_id=volunteer.id,
        request_id=req.id,
        type="new_match",
        title="New matching request",
        body="seed",
        is_read=False,
        read_at=None,
    )
    session.add(notif)
    session.commit()

    query_before, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen"}
    )
    ids_before = [r.id for r in query_before.all()]
    assert req.id in ids_before

    with app.test_request_context():
        target_url, req_id = mark_notification_opened(notif.id, volunteer.id)

    assert req_id == req.id
    assert target_url

    n2 = session.query(Notification).filter_by(id=notif.id).one()
    assert n2.is_read is True
    assert n2.read_at is not None

    s2 = (
        session.query(VolunteerRequestState)
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .one()
    )
    assert s2.seen_at is not None

    query_after, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen"}
    )
    ids_after = [r.id for r in query_after.all()]
    assert req.id not in ids_after
