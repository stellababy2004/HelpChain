from datetime import datetime, timedelta

from backend.helpchain_backend.src.models import Notification, Request, User, Volunteer
from backend.helpchain_backend.src.notifications.inapp import (
    NUDGE_COOLDOWN_HOURS,
    send_nudge_notification,
)


def test_admin_nudge_cooldown_prevents_spam(app, session):
    req_user = User(
        username="nudge_seed_user",
        email="nudge_seed_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Nudge Seed Volunteer",
        email="nudge_seed_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    req = Request(
        title="nudge seed request",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
        assigned_volunteer_id=volunteer.id,
    )
    session.add(req)
    session.commit()

    t0 = datetime.utcnow()
    assert send_nudge_notification(request_id=req.id, volunteer_id=volunteer.id, now=t0) is True
    assert send_nudge_notification(request_id=req.id, volunteer_id=volunteer.id, now=t0) is False
    assert (
        send_nudge_notification(
            request_id=req.id,
            volunteer_id=volunteer.id,
            now=t0 + timedelta(hours=NUDGE_COOLDOWN_HOURS + 1),
        )
        is True
    )

    nudge_count = (
        session.query(Notification)
        .filter_by(volunteer_id=volunteer.id, request_id=req.id, type="admin_nudge")
        .count()
    )
    # Reused row due uq_notif_vol_type_req; cooldown still allows re-send semantics.
    assert nudge_count == 1
