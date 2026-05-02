from __future__ import annotations

import os
import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from backend.helpchain_backend.src.models.magic_link_token import MagicLinkToken
from backend.helpchain_backend.src.routes import main as main_routes
from backend.models import Request, SecurityEvent, Structure


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_structure(session) -> Structure:
    structure = session.query(Structure).filter_by(slug="default").first()
    assert structure is not None
    return structure


def _create_request(session, suffix: str) -> Request:
    structure = _default_structure(session)
    req = Request(
        title=f"Magic link request {suffix}",
        description="Magic link test request",
        name="Magic Link User",
        email=f"magic.{suffix}@test.local",
        status="pending",
        priority="normal",
        category="social",
        structure_id=structure.id,
    )
    session.add(req)
    session.commit()
    return req


def _reset_magic_link_rate_limits() -> None:
    main_routes._IN_MEMORY_RL.clear()
    if hasattr(main_routes, "_IN_MEMORY_BLOCKS"):
        main_routes._IN_MEMORY_BLOCKS.clear()
    if hasattr(main_routes, "_REDIS_RL_CLIENT"):
        main_routes._REDIS_RL_CLIENT = None
    if hasattr(main_routes, "_REDIS_RL_URL"):
        main_routes._REDIS_RL_URL = None


def _post_volunteer_magic(client, email: str, remote_addr: str = "203.0.113.10"):
    payload = {
        "email": email,
        "company_fax": "",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }
    return client.post(
        "/become_volunteer",
        data=payload,
        follow_redirects=False,
        environ_overrides={"REMOTE_ADDR": remote_addr},
    )


def _submit_request_magic(
    client,
    *,
    email: str,
    suffix: str,
    remote_addr: str = "203.0.113.20",
):
    payload = {
        "name": "Security Test Request",
        "email": email,
        "phone": "0600000000",
        "category": "social",
        "urgency": "normal",
        "title": f"Security request {suffix}",
        "description": f"Security flow request {suffix}",
        "location_text": "Paris",
        "privacy_consent": "1",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }
    preview = client.post(
        "/submit_request",
        data=payload,
        follow_redirects=False,
        environ_overrides={"REMOTE_ADDR": remote_addr},
    )
    confirm = client.post(
        "/submit_request/confirm",
        data={},
        follow_redirects=False,
        environ_overrides={"REMOTE_ADDR": remote_addr},
    )
    return preview, confirm


def _create_security_event(
    session,
    *,
    event_type: str,
    ip: str | None = None,
    email: str | None = None,
    minutes_ago: int = 1,
    meta: dict | None = None,
):
    event = SecurityEvent(
        event_type=event_type,
        actor_type="anonymous",
        ip=ip,
        email_hash=_sha256_hex(email.strip().lower()) if email else None,
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        meta=meta or {},
        meta_json=None,
    )
    session.add(event)
    session.commit()
    return event


def test_request_magic_link_is_single_use(client, session):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "single-use")
    raw_token = "single-use-token"
    token_hash = _sha256_hex(raw_token)

    row = MagicLinkToken(
        purpose="request",
        email=req.email,
        request_id=req.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    session.add(row)
    session.commit()

    first = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert first.status_code in (302, 303)
    assert first.headers["Location"].endswith("/profile")

    session.expire_all()
    consumed = session.query(MagicLinkToken).filter_by(token_hash=token_hash).first()
    assert consumed is not None
    assert consumed.used_at is not None
    assert consumed.invalidated_at is None

    second = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert second.status_code == 200
    assert ("Submit a request" in second.get_data(as_text=True)) or ("Demander" in second.get_data(as_text=True)) or ("demande" in second.get_data(as_text=True).lower()) or ("HelpChain" in second.get_data(as_text=True))


def test_expired_magic_link_is_rejected_and_marked_invalid(client, session):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "expired")
    raw_token = "expired-token"
    token_hash = _sha256_hex(raw_token)

    row = MagicLinkToken(
        purpose="request",
        email=req.email,
        request_id=req.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(row)
    session.commit()

    response = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert response.status_code == 200
    assert ("Submit a request" in response.get_data(as_text=True)) or ("Demander" in response.get_data(as_text=True)) or ("demande" in response.get_data(as_text=True).lower()) or ("HelpChain" in response.get_data(as_text=True))

    session.expire_all()
    expired = session.query(MagicLinkToken).filter_by(token_hash=token_hash).first()
    assert expired is not None
    assert expired.used_at is None
    assert expired.invalidated_at is not None
    assert expired.invalidated_reason == "expired"


def test_invalid_magic_link_token_fails_safely(client):
    _reset_magic_link_rate_limits()
    response = client.get("/auth/magic/does-not-exist", follow_redirects=False)
    assert response.status_code == 200
    assert ("Submit a request" in response.get_data(as_text=True)) or ("Demander" in response.get_data(as_text=True)) or ("demande" in response.get_data(as_text=True).lower()) or ("HelpChain" in response.get_data(as_text=True))


def test_submit_request_confirm_creates_hashed_magic_link_row(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    payload = {
        "name": "Request Magic Link",
        "email": "request.magic@test.local",
        "phone": "0600000000",
        "category": "social",
        "urgency": "normal",
        "title": "Request magic link submit",
        "description": "Submit request flow should create a hashed magic link token.",
        "location_text": "Paris",
        "privacy_consent": "1",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }

    preview = client.post("/submit_request", data=payload, follow_redirects=False)
    assert preview.status_code == 200

    confirm = client.post("/submit_request/confirm", data={}, follow_redirects=False)
    assert confirm.status_code in (302, 303)

    session.expire_all()
    req = (
        session.query(Request)
        .filter_by(email="request.magic@test.local")
        .order_by(Request.id.desc())
        .first()
    )
    assert req is not None
    assert req.requester_token_hash
    assert len(req.requester_token_hash) == 64

    token_row = (
        session.query(MagicLinkToken)
        .filter_by(request_id=req.id, purpose="request")
        .order_by(MagicLinkToken.id.desc())
        .first()
    )
    assert token_row is not None
    assert token_row.token_hash
    assert len(token_row.token_hash) == 64
    assert token_row.email == "request.magic@test.local"
    assert token_row.invalidated_at is None


def test_become_volunteer_reuse_cooldown_blocks_duplicate_active_link(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "volunteer.cooldown@test.local"
    payload = {
        "email": email,
        "company_fax": "",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }

    first = client.post("/become_volunteer", data=payload, follow_redirects=False)
    assert first.status_code == 200

    second = client.post("/become_volunteer", data=payload, follow_redirects=False)
    assert second.status_code == 200

    tokens = (
        session.query(MagicLinkToken)
        .filter_by(email=email, purpose="volunteer")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(tokens) == 1
    assert tokens[0].used_at is None
    assert tokens[0].invalidated_at is None


def test_submit_request_confirm_rate_limits_magic_link_by_email(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "request.limit@test.local"

    for idx in range(4):
        payload = {
            "name": "Request Limit",
            "email": email,
            "phone": "0600000000",
            "category": "social",
            "urgency": "normal",
            "title": f"Request limit {idx}",
            "description": "Rate limit test request flow.",
            "location_text": "Paris",
            "privacy_consent": "1",
            "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
        }
        preview = client.post("/submit_request", data=payload, follow_redirects=False)
        assert preview.status_code == 200
        confirm = client.post("/submit_request/confirm", data={}, follow_redirects=False)
        assert confirm.status_code in (302, 303)

    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(email=email, purpose="request")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 3


def test_become_volunteer_rate_limits_magic_link_by_ip(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)

    for idx in range(11):
        response = _post_volunteer_magic(client, f"volunteer.ip.{idx}@test.local")
        assert response.status_code == 200

    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 5


def test_burst_attack_from_one_ip_triggers_suspicious_activity_and_soft_block(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    remote_addr = "203.0.113.77"

    for idx in range(8):
        response = _post_volunteer_magic(
            client,
            f"burst.attack.{idx}@test.local",
            remote_addr=remote_addr,
        )
        assert response.status_code == 200

    session.expire_all()
    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 5

    count_before = len(token_rows)
    blocked_response = _post_volunteer_magic(
        client,
        "burst.attack.blocked@test.local",
        remote_addr=remote_addr,
    )
    assert blocked_response.status_code == 200

    session.expire_all()
    count_after = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .count()
    )
    assert count_after == count_before

    suspicious_events = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_suspicious_activity", ip=remote_addr)
        .all()
    )
    assert suspicious_events


def test_multi_email_spray_from_one_ip_stops_early_and_keeps_generic_response(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    remote_addr = "203.0.113.88"
    response_bodies: list[str] = []

    for idx in range(7):
        response = _post_volunteer_magic(
            client,
            f"spray.attack.{idx}@test.local",
            remote_addr=remote_addr,
        )
        assert response.status_code == 200
        response_bodies.append(response.get_data(as_text=True))

    session.expire_all()
    token_count = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .count()
    )
    assert token_count == 5
    assert len(set(response_bodies)) == 1

    suspicious_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_suspicious_activity", ip=remote_addr)
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert suspicious_event is not None


def test_repeated_requests_for_same_email_log_reuse_blocked(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "reuse.blocked@test.local"

    first = _post_volunteer_magic(client, email, remote_addr="203.0.113.99")
    second = _post_volunteer_magic(client, email, remote_addr="203.0.113.99")
    third = _post_volunteer_magic(client, email, remote_addr="203.0.113.99")
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    session.expire_all()
    tokens = session.query(MagicLinkToken).filter_by(email=email, purpose="volunteer").all()
    assert len(tokens) == 1

    reuse_events = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_reuse_blocked")
        .order_by(SecurityEvent.id.desc())
        .all()
    )
    if reuse_events:
        assert any(
            (event.meta or {}).get("purpose") == "volunteer" for event in reuse_events
        )


def test_replay_attack_on_consumed_token_logs_consumed_and_rejected(client, session):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "replay-attack")
    raw_token = "replay-attack-token"
    token_hash = _sha256_hex(raw_token)

    session.add(
        MagicLinkToken(
            purpose="request",
            email=req.email,
            request_id=req.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    session.commit()

    first = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    second = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert first.status_code in (302, 303)
    assert second.status_code == 200

    session.expire_all()
    consumed_token = session.query(MagicLinkToken).filter_by(token_hash=token_hash).first()
    assert consumed_token is not None
    assert consumed_token.used_at is not None
    assert consumed_token.invalidated_at is None

    consumed_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_consumed")
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    rejected_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_rejected")
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert consumed_event is not None
    assert rejected_event is not None
    assert rejected_event.meta["reason"] == "already_used"


def test_expired_token_attack_logs_rejection_reason(client, session):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "expired-attack")
    raw_token = "expired-attack-token"
    token_hash = _sha256_hex(raw_token)

    session.add(
        MagicLinkToken(
            purpose="request",
            email=req.email,
            request_id=req.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    session.commit()

    response = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert response.status_code == 200

    session.expire_all()
    expired = session.query(MagicLinkToken).filter_by(token_hash=token_hash).first()
    assert expired is not None
    assert expired.invalidated_reason == "expired"

    rejected_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_rejected")
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert rejected_event is not None
    assert rejected_event.meta["reason"] == "expired"


def test_distributed_attack_across_ips_triggers_email_based_limits(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "distributed.attack@test.local"

    for idx in range(5):
        preview, confirm = _submit_request_magic(
            client,
            email=email,
            suffix=f"distributed-{idx}",
            remote_addr=f"203.0.113.{120 + idx}",
        )
        assert preview.status_code == 200
        assert confirm.status_code in (302, 303)

    session.expire_all()
    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(email=email, purpose="request")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 3

    rate_limited_events = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_rate_limited")
        .filter(SecurityEvent.email_hash == _sha256_hex(email))
        .all()
    )
    assert rate_limited_events


def test_rotating_ip_and_email_attack_is_observable_and_bounded(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)

    for idx in range(6):
        response = _post_volunteer_magic(
            client,
            f"rotating.attack.{idx}@test.local",
            remote_addr=f"203.0.114.{idx + 1}",
        )
        assert response.status_code == 200

    session.expire_all()
    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 6

    attempt_events = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_attempt")
        .all()
    )
    assert len(attempt_events) == 6


def test_rate_limit_with_redis_matches_expected_behavior(
    client, session, monkeypatch
):
    redis_url = (os.getenv("REDIS_URL") or "").strip()
    if not redis_url:
        pytest.skip("REDIS_URL not configured")

    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    monkeypatch.setenv("REDIS_URL", redis_url)
    remote_addr = "203.0.115.50"

    for idx in range(11):
        response = _post_volunteer_magic(
            client,
            f"redis.parity.{idx}@test.local",
            remote_addr=remote_addr,
        )
        assert response.status_code == 200

    session.expire_all()
    token_rows = (
        session.query(MagicLinkToken)
        .filter_by(purpose="volunteer")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(token_rows) == 5

    suspicious_events = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_suspicious_activity", ip=remote_addr)
        .all()
    )
    assert suspicious_events


def test_magic_link_risk_score_blocks_high_risk_ip(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    remote_addr = "203.0.116.10"
    blocked_email = "high.risk.blocked@test.local"

    _create_security_event(
        session,
        event_type="magic_link_suspicious_activity",
        ip=remote_addr,
        email=blocked_email,
    )

    response = _post_volunteer_magic(client, blocked_email, remote_addr=remote_addr)
    assert response.status_code == 200

    session.expire_all()
    blocked_tokens = (
        session.query(MagicLinkToken)
        .filter_by(email=blocked_email, purpose="volunteer")
        .all()
    )
    assert len(blocked_tokens) == 0

    risk_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_risk_blocked", ip=remote_addr)
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert risk_event is not None
    assert (risk_event.meta or {}).get("risk_score", 0) >= 4
    assert "recent_suspicious" in ((risk_event.meta or {}).get("signals") or [])


def test_magic_link_progressive_penalty_increases_block_duration():
    assert main_routes._magic_link_block_duration_for_score(0) == 0
    assert main_routes._magic_link_block_duration_for_score(3) == 0
    assert main_routes._magic_link_block_duration_for_score(4) == 10 * 60
    assert main_routes._magic_link_block_duration_for_score(6) == 10 * 60
    assert main_routes._magic_link_block_duration_for_score(7) == 60 * 60
    assert main_routes._magic_link_block_duration_for_score(9) == 60 * 60
    assert main_routes._magic_link_block_duration_for_score(10) == 24 * 60 * 60


def test_magic_link_shadow_block_keeps_generic_response(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    remote_addr = "203.0.116.20"
    blocked_email = "shadow.blocked@test.local"
    allowed_email = "shadow.allowed@test.local"

    _create_security_event(
        session,
        event_type="magic_link_suspicious_activity",
        ip=remote_addr,
        email=blocked_email,
    )

    blocked_response = _post_volunteer_magic(
        client,
        blocked_email,
        remote_addr=remote_addr,
    )
    allowed_response = _post_volunteer_magic(
        client,
        allowed_email,
        remote_addr="203.0.116.21",
    )
    assert blocked_response.status_code == 200
    assert allowed_response.status_code == 200
    assert blocked_response.get_data(as_text=True) == allowed_response.get_data(as_text=True)

    session.expire_all()
    assert (
        session.query(MagicLinkToken)
        .filter_by(email=blocked_email, purpose="volunteer")
        .count()
        == 0
    )
    assert (
        session.query(MagicLinkToken)
        .filter_by(email=allowed_email, purpose="volunteer")
        .count()
        == 1
    )


def test_magic_link_risk_block_logs_expected_event(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    remote_addr = "203.0.116.30"
    blocked_email = "risk.log@test.local"

    _create_security_event(
        session,
        event_type="magic_link_rate_limited",
        ip=remote_addr,
        email=blocked_email,
        meta={"purpose": "volunteer"},
    )
    _create_security_event(
        session,
        event_type="magic_link_suspicious_activity",
        ip=remote_addr,
        email=blocked_email,
    )

    response = _post_volunteer_magic(client, blocked_email, remote_addr=remote_addr)
    assert response.status_code == 200

    session.expire_all()
    risk_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_risk_blocked", ip=remote_addr)
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert risk_event is not None
    assert risk_event.email_hash == _sha256_hex(blocked_email)
    assert (risk_event.meta or {}).get("purpose") == "volunteer"
    assert (risk_event.meta or {}).get("risk_score", 0) >= 6
    assert "recent_rate_limit" in ((risk_event.meta or {}).get("signals") or [])
    assert "recent_suspicious" in ((risk_event.meta or {}).get("signals") or [])
    assert (risk_event.meta or {}).get("block_duration_sec") == 60 * 60

