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

    query, _status, _q, _risk = build_requests_query(Request.query, {"risk": "notseen"})
    ids = [r.id for r in query.all()]

    assert r1.id in ids
