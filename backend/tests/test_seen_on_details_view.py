from backend.helpchain_backend.src.models import (
    Request,
    User,
    Volunteer,
    VolunteerRequestState,
)
from backend.helpchain_backend.src.notifications.inapp import (
    mark_request_seen_for_volunteer,
)


def test_mark_request_seen_for_volunteer_sets_seen_at_idempotently(app, session):
    req_user = User(
        username="seen_seed_user",
        email="seen_seed_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Seen Seed Volunteer",
        email="seen_seed_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    req = Request(
        title="seed seen request",
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
        notified_at=None,
        seen_at=None,
    )
    session.add(state)
    session.commit()

    changed = mark_request_seen_for_volunteer(
        request_id=req.id, volunteer_id=volunteer.id
    )
    assert changed is True

    state_after = (
        session.query(VolunteerRequestState)
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .one()
    )
    assert state_after.seen_at is not None

    changed_again = mark_request_seen_for_volunteer(
        request_id=req.id, volunteer_id=volunteer.id
    )
    assert changed_again is False


def test_mark_request_seen_for_volunteer_does_not_create_missing_state(app, session):
    req_user = User(
        username="seen_missing_user",
        email="seen_missing_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Seen Missing Volunteer",
        email="seen_missing_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    req = Request(
        title="seed missing state request",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add(req)
    session.commit()

    changed = mark_request_seen_for_volunteer(
        request_id=req.id, volunteer_id=volunteer.id
    )
    assert changed is False

    state = (
        session.query(VolunteerRequestState)
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .one_or_none()
    )
    assert state is None
