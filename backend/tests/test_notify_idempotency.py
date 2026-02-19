from backend.helpchain_backend.src.models import (
    Notification,
    Request,
    User,
    Volunteer,
    VolunteerRequestState,
)
from backend.helpchain_backend.src.notifications.inapp import (
    ensure_new_match_notifications,
)


def test_ensure_new_match_notifications_idempotent(app, session):
    req_user = User(
        username="notify_seed_user",
        email="notify_seed_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Notify Seed Volunteer",
        email="notify_seed_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    req = Request(
        title="seed notify request",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add(req)
    session.commit()

    ensure_new_match_notifications(volunteer_id=volunteer.id, request_rows=[req])

    n1 = (
        session.query(Notification)
        .filter_by(volunteer_id=volunteer.id, request_id=req.id, type="new_match")
        .count()
    )
    assert n1 == 1

    notified_before = (
        session.query(VolunteerRequestState.notified_at)
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .scalar()
    )
    assert notified_before is not None

    ensure_new_match_notifications(volunteer_id=volunteer.id, request_rows=[req])
    ensure_new_match_notifications(volunteer_id=volunteer.id, request_rows=[req])

    n2 = (
        session.query(Notification)
        .filter_by(volunteer_id=volunteer.id, request_id=req.id, type="new_match")
        .count()
    )
    assert n2 == 1

    notified_after = (
        session.query(VolunteerRequestState.notified_at)
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .scalar()
    )
    assert notified_after == notified_before
