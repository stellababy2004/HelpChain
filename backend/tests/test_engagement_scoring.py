from datetime import datetime, timedelta, timezone

from backend.helpchain_backend.src.models import (
    Request,
    RequestActivity,
    User,
    Volunteer,
    VolunteerRequestState,
)
from backend.helpchain_backend.src.routes.admin import get_volunteer_engagement_score


def test_volunteer_engagement_scoring_medium(app, session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    req_user = User(
        username="engagement_seed_user",
        email="engagement_seed_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    volunteer = Volunteer(
        name="Engagement Volunteer",
        email="engagement_volunteer@test.local",
        location="Sofia",
        availability="weekday-evening",
        skills="food,delivery",
        is_active=True,
        volunteer_onboarded=True,
    )
    session.add(volunteer)
    session.flush()

    r1 = Request(
        title="engagement request 1",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    r2 = Request(
        title="engagement request 2",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add_all([r1, r2])
    session.flush()

    session.add_all(
        [
            VolunteerRequestState(
                request_id=r1.id,
                volunteer_id=volunteer.id,
                notified_at=now - timedelta(hours=10),
                seen_at=now - timedelta(hours=9),
            ),
            VolunteerRequestState(
                request_id=r2.id,
                volunteer_id=volunteer.id,
                notified_at=now - timedelta(hours=73),
                seen_at=None,
            ),
            RequestActivity(
                request_id=r1.id,
                volunteer_id=volunteer.id,
                action="volunteer_can_help",
                old_value=None,
                new_value="CAN_HELP",
            ),
        ]
    )
    session.commit()

    score = get_volunteer_engagement_score(volunteer.id, now=now)

    assert score["seen_within_24h"] == 1
    assert score["not_seen_72h"] == 1
    assert score["can_help"] == 1
    assert score["cant_help"] == 0
    assert score["score"] == 2
    assert score["label"] == "Medium"
