from datetime import datetime, timedelta, timezone

from backend.helpchain_backend.src.models import Request, User, VolunteerRequestState
from backend.helpchain_backend.src.routes.admin import build_requests_query


def test_risk_notseen_only_notified_not_seen_older_than_24h(app, session):
    now = datetime.now(timezone.utc)

    req_user = User(
        username="risk_seed_user",
        email="risk_seed_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    r1 = Request(
        title="seed risk request",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add(r1)
    session.flush()

    s1 = VolunteerRequestState(
        request_id=r1.id,
        volunteer_id=1,
        notified_at=now - timedelta(hours=25),
        seen_at=None,
    )
    session.add(s1)
    session.commit()

    query, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen"}, legacy=True
    )
    ids = [r.id for r in query.all()]

    assert r1.id in ids


def test_risk_notseen_tiers_24_48_72(app, session):
    now = datetime.now(timezone.utc)

    req_user = User(
        username="risk_tier_user",
        email="risk_tier_user@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(req_user)
    session.flush()

    r24 = Request(
        title="risk tier 24",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    r48 = Request(
        title="risk tier 48",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    r72 = Request(
        title="risk tier 72",
        description="seed",
        status="open",
        category="general",
        user_id=req_user.id,
    )
    session.add_all([r24, r48, r72])
    session.flush()

    session.add_all(
        [
            VolunteerRequestState(
                request_id=r24.id,
                volunteer_id=1,
                notified_at=now - timedelta(hours=25),
                seen_at=None,
            ),
            VolunteerRequestState(
                request_id=r48.id,
                volunteer_id=2,
                notified_at=now - timedelta(hours=49),
                seen_at=None,
            ),
            VolunteerRequestState(
                request_id=r72.id,
                volunteer_id=3,
                notified_at=now - timedelta(hours=73),
                seen_at=None,
            ),
        ]
    )
    session.commit()

    q24, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen24"}, legacy=True
    )
    ids24 = {r.id for r in q24.all()}
    assert r24.id in ids24
    assert r48.id in ids24
    assert r72.id in ids24

    q48, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen48"}, legacy=True
    )
    ids48 = {r.id for r in q48.all()}
    assert r24.id not in ids48
    assert r48.id in ids48
    assert r72.id in ids48

    q72, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen72"}, legacy=True
    )
    ids72 = {r.id for r in q72.all()}
    assert r24.id not in ids72
    assert r48.id not in ids72
    assert r72.id in ids72

    q_alias, _status, _q, _risk = build_requests_query(
        Request.query, {"risk": "notseen"}, legacy=True
    )
    ids_alias = {r.id for r in q_alias.all()}
    assert ids_alias == ids24
