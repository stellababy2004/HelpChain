from __future__ import annotations

import os
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from sqlalchemy.sql.dml import Update

from backend.helpchain_backend.src.models.magic_link_token import MagicLinkToken
from backend.helpchain_backend.src.routes import main as main_routes
from backend.models import (
    Request,
    SecurityEvent,
    Structure,
    StructureCoverageArea,
    StructureService,
    Volunteer,
)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_structure(session) -> Structure:
    structure = session.query(Structure).filter_by(slug="default").first()
    assert structure is not None
    return structure


def _ensure_public_intake_route(session) -> None:
    structure = _default_structure(session)
    structure.status = "active"

    coverage = (
        session.query(StructureCoverageArea)
        .filter_by(
            structure_id=structure.id,
            postal_code="92100",
            is_active=True,
        )
        .first()
    )
    if coverage is None:
        session.add(
            StructureCoverageArea(
                structure_id=structure.id,
                area_type="city",
                name="Boulogne-Billancourt",
                postal_code="92100",
                is_active=True,
            )
        )

    service = (
        session.query(StructureService)
        .filter_by(
            structure_id=structure.id,
            code="admin",
            is_active=True,
        )
        .first()
    )
    if service is None:
        session.add(
            StructureService(
                structure_id=structure.id,
                code="admin",
                name="Accompagnement administratif",
                is_active=True,
            )
        )

    session.commit()


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


def _consume_requester_link(client, session, req):
    raw_token = f"profile-token-{req.id}"
    session.add(
        MagicLinkToken(
            purpose="request",
            email=req.email,
            request_id=req.id,
            token_hash=_sha256_hex(raw_token),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    session.commit()
    response = client.get(f"/auth/magic/{raw_token}")
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/profile")


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
        "category": "admin_help",
        "urgency": "normal",
        "title": f"Security request {suffix}",
        "description": f"Security flow request {suffix}",
        "location_text": "Boulogne-Billancourt",
        "postcode": "92100",
        "city": "Boulogne-Billancourt",
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


def test_magic_link_claim_uses_atomic_conditional_update(client, monkeypatch):
    raw_token = "atomic-claim-token"
    token_hash = _sha256_hex(raw_token)
    captured = {}

    class _Result:
        rowcount = 1

    def fake_execute(statement):
        captured["statement"] = statement
        return _Result()

    monkeypatch.setattr(main_routes.db.session, "execute", fake_execute)
    row = MagicLinkToken(
        id=123,
        purpose="request",
        email="atomic.claim@test.local",
        request_id=456,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    with client.application.test_request_context(
        f"/auth/magic/{raw_token}",
        headers={"User-Agent": "atomic-test"},
        environ_base={"REMOTE_ADDR": "203.0.113.210"},
    ):
        assert main_routes._claim_magic_link_token(
            row,
            token_hash=token_hash,
            now=datetime.now(UTC),
        )

    statement = captured["statement"]
    assert isinstance(statement, Update)
    compiled = str(statement).lower()
    assert compiled.startswith("update magic_link_tokens")
    assert "token_hash" in compiled
    assert "purpose in" in compiled
    assert "used_at is null" in compiled
    assert "invalidated_at is null" in compiled
    assert "expires_at >" in compiled


def test_atomic_claim_loser_is_rejected_without_authentication(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "atomic-loser")
    raw_token = "atomic-loser-token"
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

    def lose_race(ml, *, token_hash, now):
        raced = session.query(MagicLinkToken).filter_by(token_hash=token_hash).one()
        raced.used_at = now
        session.commit()
        return False

    monkeypatch.setattr(main_routes, "_claim_magic_link_token", lose_race)

    response = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)

    assert response.status_code == 200
    with client.session_transaction() as flask_session:
        assert not flask_session.get("requester_authenticated")
        assert not flask_session.get("requester_verified_email")

    rejected_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_rejected")
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert rejected_event is not None
    assert rejected_event.meta["reason"] == "already_used"


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



def test_submit_request_missing_privacy_consent_shows_visible_error(client, monkeypatch):
    # Reproduce production behaviour: privacy consent validation is skipped
    # when the Flask app is running with TESTING=True.
    monkeypatch.setitem(client.application.config, "TESTING", False)

    payload = {
        "name": "Pilot User",
        "email": "pilot@example.org",
        "phone": "",
        "category": "orientation",
        "urgency": "normal",
        "title": "School event volunteer coordination",
        "description": (
            "The school is preparing an event and needs volunteers "
            "to help with organisation."
        ),
        "postcode": "92100",
        "city": "Boulogne-Billancourt",
        "country": "France",
    }

    response = client.post(
        "/submit_request",
        data=payload,
        follow_redirects=False,
    )

    assert response.status_code == 400

    body = response.get_data(as_text=True)
    assert (
        "Veuillez accepter la Politique de confidentialit\u00e9 (RGPD) pour continuer."
        in body
    )


def test_submit_request_confirm_creates_hashed_magic_link_row(client, session, monkeypatch, caplog):
    caplog.set_level("INFO")
    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )
    payload = {
        "name": "Request Magic Link",
        "email": "request.magic@test.local",
        "phone": "0600000000",
        "category": "admin_help",
        "urgency": "normal",
        "title": "Request magic link submit",
        "description": "Submit request flow should create a hashed magic link token.",
        "location_text": "Boulogne-Billancourt",
        "postcode": "92100",
        "city": "Boulogne-Billancourt",
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
    assert len(sent) == 1
    magic_url = sent[0][3]["magic_link_url"]
    raw_token = urlsplit(magic_url).path.rsplit("/", 1)[-1]
    assert raw_token and _sha256_hex(raw_token) == token_row.token_hash
    assert raw_token not in caplog.text
    assert magic_url not in caplog.text
    assert "request.magic@test.local" not in caplog.text
    assert "r***@test.local" in caplog.text


def test_submit_request_confirm_dev_magic_link_uses_request_host(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    monkeypatch.setitem(
        client.application.config, "PUBLIC_BASE_URL", "https://helpchain.live"
    )
    monkeypatch.setitem(client.application.config, "FLASK_ENV", "development")
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )
    payload = {
        "name": "Local Magic Link",
        "email": "local.magic@test.local",
        "phone": "0600000000",
        "category": "admin_help",
        "urgency": "normal",
        "title": "Local request magic link",
        "description": "Local magic link should resolve to the local app.",
        "location_text": "Boulogne-Billancourt",
        "postcode": "92100",
        "city": "Boulogne-Billancourt",
        "privacy_consent": "1",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }

    preview = client.post(
        "/submit_request",
        data=payload,
        follow_redirects=False,
        base_url="http://127.0.0.1:5000",
    )
    assert preview.status_code == 200

    confirm = client.post(
        "/submit_request/confirm",
        data={},
        follow_redirects=False,
        base_url="http://127.0.0.1:5000",
    )
    assert confirm.status_code in (302, 303)

    assert len(sent) == 1
    magic_url = sent[0][3]["magic_link_url"]
    parsed = urlsplit(magic_url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:5000"
    assert parsed.path.startswith("/auth/magic/")
    assert "helpchain.live" not in magic_url

    accepted = client.get(parsed.path, base_url="http://127.0.0.1:5000")
    assert accepted.status_code == 303
    assert accepted.headers["Location"].endswith("/profile")


def test_configured_production_magic_link_url_remains_helpchain_live(
    client, monkeypatch
):
    monkeypatch.setitem(
        client.application.config, "PUBLIC_BASE_URL", "https://helpchain.live"
    )
    monkeypatch.setitem(client.application.config, "APP_ENV", "production")

    with client.application.test_request_context(
        "/", base_url="http://127.0.0.1:5000"
    ):
        magic_url = main_routes._magic_link_url("production-token")

    assert magic_url == "https://helpchain.live/auth/magic/production-token"


@pytest.mark.parametrize("preexisting", [False, True])
def test_volunteer_magic_link_success_sets_only_volunteer_session(
    client,
    session,
    preexisting,
):
    _reset_magic_link_rate_limits()
    email = "volunteer.success@test.local"
    raw_token = f"volunteer-success-{preexisting}"
    token_hash = _sha256_hex(raw_token)
    existing = None
    if preexisting:
        existing = Volunteer(email=email.upper(), is_active=True)
        session.add(existing)
        session.flush()

    session.add(
        MagicLinkToken(
            purpose="volunteer",
            email=email,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    session.commit()
    existing_id = existing.id if existing is not None else None

    with client.session_transaction() as flask_session:
        flask_session["requester_authenticated"] = True
        flask_session["requester_verified_email"] = "requester@test.local"
        flask_session["admin_logged_in"] = True
        flask_session["volunteer_next"] = "https://evil.example/steal"

    first = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)

    assert first.status_code == 303
    assert first.headers["Location"].endswith("/volunteer/dashboard")
    assert "evil.example" not in first.headers["Location"]

    session.expire_all()
    volunteers = session.query(Volunteer).filter(Volunteer.email.ilike(email)).all()
    assert len(volunteers) == 1
    volunteer = volunteers[0]
    if existing_id is not None:
        assert volunteer.id == existing_id

    with client.session_transaction() as flask_session:
        assert flask_session["volunteer_id"] == volunteer.id
        assert flask_session["volunteer_logged_in"] is True
        assert not flask_session.get("requester_authenticated")
        assert not flask_session.get("requester_verified_email")
        assert not flask_session.get("admin_logged_in")

    second = client.get(f"/auth/magic/{raw_token}", follow_redirects=False)
    assert second.status_code == 200
    rejected_event = (
        session.query(SecurityEvent)
        .filter_by(event_type="magic_link_rejected")
        .order_by(SecurityEvent.id.desc())
        .first()
    )
    assert rejected_event is not None
    assert rejected_event.meta["reason"] == "already_used"


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


def test_volunteer_magic_link_logs_mask_email(client, monkeypatch, caplog):
    caplog.set_level("INFO")
    _reset_magic_link_rate_limits()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "volunteer.logging@test.local"

    response = _post_volunteer_magic(client, email, remote_addr="203.0.113.211")

    assert response.status_code == 200
    assert email not in caplog.text
    assert "v***@test.local" in caplog.text


def test_submit_request_confirm_rate_limits_magic_link_by_email(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)
    email = "request.limit@test.local"

    for idx in range(4):
        payload = {
            "name": "Request Limit",
            "email": email,
            "phone": "0600000000",
            "category": "admin_help",
            "urgency": "normal",
            "title": f"Request limit {idx}",
            "description": "Rate limit test request flow.",
            "location_text": "Boulogne-Billancourt",
            "postcode": "92100",
            "city": "Boulogne-Billancourt",
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
    _ensure_public_intake_route(session)
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


@pytest.mark.parametrize("allow_default_fallback", [False, True])
def test_request_magic_link_resend_issues_token_and_sends_email(
    client, session, monkeypatch, allow_default_fallback
):
    """Resend must issue a request token, send one email, and stay in verification."""
    _reset_magic_link_rate_limits()
    req = _create_request(session, "resend")
    structure = Structure(name="Public intake", slug="resend-intake")
    session.add(structure)
    session.flush()
    req.structure_id = structure.id
    session.commit()
    monkeypatch.setitem(
        client.application.config, "ALLOW_DEFAULT_TENANT_FALLBACK", allow_default_fallback
    )

    sent_emails = []

    def fake_send_notification_email(*args, **kwargs):
        sent_emails.append((args, kwargs))
        return True

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        fake_send_notification_email,
    )

    with client.session_transaction() as flask_session:
        flask_session["requester_email"] = req.email
        flask_session["last_request_id"] = req.id

    response = client.post(
        "/submit_request/resend",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["Location"].endswith("/submit_request/check_email")

    session.expire_all()

    tokens = (
        session.query(MagicLinkToken)
        .filter_by(
            purpose="request",
            email=req.email,
            request_id=req.id,
        )
        .order_by(MagicLinkToken.id.asc())
        .all()
    )

    assert len(tokens) == 1
    assert tokens[0].token_hash
    assert tokens[0].used_at is None
    assert tokens[0].invalidated_at is None

    assert len(sent_emails) == 1

    args, kwargs = sent_emails[0]
    assert args[0] == req.email
    assert args[2] == "emails/magic_link.html"
    assert args[3]["request_id"] == req.id
    assert "/auth/magic/" in args[3]["magic_link_url"]
    assert kwargs["purpose"] == "request_magic_link"


def test_request_magic_link_resend_dev_magic_link_uses_request_host(
    client, session, monkeypatch
):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "resend-local-url")
    monkeypatch.setitem(
        client.application.config, "PUBLIC_BASE_URL", "https://helpchain.live"
    )
    monkeypatch.setitem(client.application.config, "FLASK_ENV", "development")
    sent_emails = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent_emails.append(args),
    )

    with client.session_transaction(
        base_url="http://127.0.0.1:5000"
    ) as flask_session:
        flask_session["requester_email"] = req.email
        flask_session["last_request_id"] = req.id

    response = client.post(
        "/submit_request/resend",
        follow_redirects=False,
        base_url="http://127.0.0.1:5000",
    )

    assert response.status_code == 303
    assert len(sent_emails) == 1
    magic_url = sent_emails[0][3]["magic_link_url"]
    parsed = urlsplit(magic_url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:5000"
    assert parsed.path.startswith("/auth/magic/")
    assert "helpchain.live" not in magic_url


@pytest.mark.parametrize("expired", [False, True])
def test_request_magic_link_resend_rotates_submitted_token(
    client, session, monkeypatch, expired, caplog
):
    caplog.set_level("INFO")
    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    monkeypatch.setitem(client.application.config, "ALLOW_DEFAULT_TENANT_FALLBACK", False)
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )
    email = f"resend.submitted.{expired}@test.local".lower()
    preview, confirm = _submit_request_magic(client, email=email, suffix="resend")
    assert preview.status_code == 200
    assert confirm.headers["Location"].endswith("/submit_request/check_email")
    assert client.get(confirm.headers["Location"]).status_code == 200
    session.expire_all()
    with client.session_transaction() as flask_session:
        request_id = flask_session["last_request_id"]
    req = session.get(Request, request_id)
    assert req is not None
    assert req.email == email
    request_count = session.query(Request).count()
    old = session.query(MagicLinkToken).filter_by(request_id=request_id).one()
    old.created_at = datetime.now(UTC) - timedelta(minutes=16 if expired else 3)
    old.expires_at = old.created_at + timedelta(minutes=15)
    session.commit()
    old_expiry = old.expires_at
    old_path = urlsplit(sent[0][3]["magic_link_url"]).path

    response = client.post("/submit_request/resend", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/submit_request/check_email")
    assert client.get(response.headers["Location"]).status_code == 200
    session.expire_all()
    tokens = (
        session.query(MagicLinkToken)
        .filter_by(request_id=request_id, purpose="request")
        .order_by(MagicLinkToken.id.asc())
        .all()
    )
    assert len(tokens) == 2
    old, new = tokens
    assert old.expires_at == old_expiry
    if not expired:
        assert old.invalidated_at is not None
        assert old.invalidated_reason == "superseded"
    assert new.token_hash != old.token_hash
    assert new.email == email
    assert new.used_at is None
    assert new.invalidated_at is None
    assert timedelta(minutes=14, seconds=55) < new.expires_at - new.created_at <= timedelta(minutes=15)
    assert session.get(Request, request_id).requester_token_hash == new.token_hash
    assert session.query(Request).count() == request_count
    assert len(sent) == 2
    assert sent[1][0] == email
    assert sent[1][3]["request_id"] == request_id
    new_path = urlsplit(sent[1][3]["magic_link_url"]).path
    assert new_path != old_path
    for message in sent:
        magic_url = message[3]["magic_link_url"]
        raw_token = urlsplit(magic_url).path.rsplit("/", 1)[-1]
        assert raw_token not in caplog.text
        assert magic_url not in caplog.text

    # The old link stays invalid, and only the new link authenticates the requester.
    assert client.get(old_path, follow_redirects=False).status_code == 200
    with client.session_transaction() as flask_session:
        assert not flask_session.get("requester_authenticated")
    accepted = client.get(new_path, follow_redirects=False)
    assert accepted.status_code == 303
    assert accepted.headers["Location"].endswith("/profile")
    with client.session_transaction() as flask_session:
        assert flask_session["requester_authenticated"] is True
        assert flask_session["last_request_id"] == request_id
    session.expire_all()
    assert new.used_at is not None
    assert old.used_at is None
    assert old.invalidated_at is not None
    assert old.invalidated_reason == ("expired" if expired else "superseded")
    assert session.query(Request).count() == request_count


@pytest.mark.parametrize("suppression", ["cooldown", "email_limit", "ip_limit", "risk"])
def test_request_magic_link_resend_preserves_send_suppression(
    client, session, monkeypatch, suppression
):
    _reset_magic_link_rate_limits()
    monkeypatch.setitem(client.application.config, "ALLOW_DEFAULT_TENANT_FALLBACK", False)
    req = _create_request(session, "resend-suppression")
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )
    now = datetime.now(UTC)
    old = MagicLinkToken(
        purpose="request", email=req.email, request_id=req.id,
        token_hash=_sha256_hex("resend-suppression"),
        created_at=now if suppression == "cooldown" else now - timedelta(minutes=3),
        expires_at=now + timedelta(minutes=12),
    )
    session.add(old)
    session.commit()
    ip = "203.0.113.42"
    if suppression in {"email_limit", "ip_limit"}:
        key, limit = (
            (f"ml:issue:email:{req.email}", 3)
            if suppression == "email_limit" else (f"ml:issue:ip:{ip}", 10)
        )
        for _ in range(limit):
            assert main_routes._rate_limit_check(key, limit=limit, window_sec=900)[0]
    elif suppression == "risk":
        _create_security_event(
            session, event_type="magic_link_suspicious_activity", ip=ip, email=req.email
        )
    with client.session_transaction() as flask_session:
        flask_session["requester_email"] = req.email
        flask_session["last_request_id"] = req.id

    response = client.post(
        "/submit_request/resend", environ_overrides={"REMOTE_ADDR": ip}
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/submit_request/check_email")
    assert client.get(response.headers["Location"]).status_code == 200
    assert not sent
    session.expire_all()
    assert session.query(MagicLinkToken).filter_by(request_id=req.id).count() == 1
    assert old.invalidated_at is None
    assert old.used_at is None


@pytest.mark.parametrize("session_state", ["missing", "wrong_email", "wrong_id"])
def test_request_magic_link_resend_requires_matching_session(
    client, session, monkeypatch, session_state
):
    _reset_magic_link_rate_limits()
    req = _create_request(session, "resend-session")
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )
    if session_state != "missing":
        with client.session_transaction() as flask_session:
            flask_session["requester_email"] = (
                "different@test.local" if session_state == "wrong_email" else req.email
            )
            flask_session["last_request_id"] = (
                -1 if session_state == "wrong_id" else req.id
            )

    response = client.post(
        "/submit_request/resend",
        data={"requester_email": req.email, "last_request_id": req.id},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/submit_request")
    assert not sent
    assert session.query(MagicLinkToken).filter_by(request_id=req.id).count() == 0


@pytest.mark.parametrize("allow_fallback", [True, False])
def test_requester_profile_public_partner_intake_resend_and_consume(
    client, session, monkeypatch, allow_fallback
):
    from urllib.parse import urlsplit

    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    default_id = _default_structure(session).id
    partner = Structure(name="Profile Partner", slug="profile-partner", status="active")
    session.add(partner)
    session.flush()
    coverage = session.query(StructureCoverageArea).filter_by(structure_id=default_id).one()
    service = session.query(StructureService).filter_by(structure_id=default_id).one()
    coverage.structure_id = partner.id
    service.structure_id = partner.id
    session.commit()
    partner_id, service_id = partner.id, service.id
    monkeypatch.setitem(
        client.application.config, "ALLOW_DEFAULT_TENANT_FALLBACK", allow_fallback
    )
    sent = []
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: sent.append(args),
    )

    preview, confirm = _submit_request_magic(
        client, email="partner.requester@test.local", suffix="partner-profile"
    )
    assert preview.status_code == 200
    assert confirm.headers["Location"].endswith("/submit_request/check_email")
    assert client.get(confirm.headers["Location"]).status_code == 200
    with client.session_transaction() as flask_session:
        request_id = flask_session["last_request_id"]
        assert not flask_session.get("requester_verified_email")
    req = session.get(Request, request_id)
    assert req.structure_id == partner_id != default_id
    assert req.service_id == service_id
    assert client.get("/profile").status_code == 302

    old = session.query(MagicLinkToken).filter_by(request_id=request_id).one()
    old.created_at = datetime.now(UTC) - timedelta(minutes=3)
    session.commit()
    resend = client.post("/submit_request/resend")
    assert resend.status_code == 303
    assert len(sent) == 2
    assert client.get("/profile").status_code == 302
    response = client.get(urlsplit(sent[-1][3]["magic_link_url"]).path, follow_redirects=True)
    assert response.status_code == 200
    assert req.title in response.get_data(as_text=True)
    with client.session_transaction() as flask_session:
        assert flask_session["requester_verified_email"] == req.email
        assert flask_session["requester_authenticated"] is True
    session.expire_all()
    assert session.get(Request, request_id).structure_id == partner_id
    assert session.get(Request, request_id).service_id == service_id


@pytest.mark.parametrize(
    "statuses", [("open", "done"), ("pending", "pending"), ("in_progress", "cancelled")]
)
def test_requester_profile_verified_email_spans_structures_and_scopes_counts(client, session, statuses):
    own = _create_request(session, "profile-own-default")
    partner = Structure(name="Second Partner", slug="profile-second")
    session.add(partner)
    session.flush()
    other_own = _create_request(session, "profile-own-partner")
    stranger = _create_request(session, "profile-stranger-default")
    other_stranger = _create_request(session, "profile-stranger-partner")
    own.status = statuses[0]
    other_own.email = own.email.upper()
    other_own.structure_id = partner.id
    other_own.status = statuses[1]
    stranger.status = statuses[0]
    other_stranger.structure_id = partner.id
    other_stranger.status = statuses[1]
    session.commit()

    _consume_requester_link(client, session, other_own)
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert own.title in html and other_own.title in html
    assert stranger.title not in html and other_stranger.title not in html
    for status in ("pending", "open", "in_progress", "done", "cancelled"):
        assert f">{status}: {statuses.count(status)}</span>" in html

    # Consuming another identity's link replaces, rather than combines, access.
    _consume_requester_link(client, session, stranger)
    html = client.get("/profile").get_data(as_text=True)
    assert stranger.title in html
    assert own.title not in html and other_own.title not in html


@pytest.mark.parametrize("source", ["query", "form", "pending_session"])
def test_requester_profile_ignores_unverified_identity_and_scope_inputs(client, session, source):
    own = _create_request(session, "profile-input-own")
    victim = _create_request(session, "profile-input-victim")
    partner = Structure(name="Victim Partner", slug="profile-victim")
    session.add(partner)
    session.flush()
    victim.structure_id = partner.id
    session.commit()
    _consume_requester_link(client, session, own)
    inputs = {
        "request_id": victim.id,
        "last_request_id": victim.id,
        "structure_id": partner.id,
        "email": victim.email,
        "requester_email": victim.email,
    }
    kwargs = {}
    if source == "pending_session":
        # Model mutable intake state, not forgery of Flask's signed cookie.
        with client.session_transaction() as flask_session:
            flask_session.update(inputs)
    else:
        inputs["requester_verified_email"] = victim.email
        inputs["requester_authenticated"] = "true"
        kwargs["query_string" if source == "query" else "data"] = inputs
    response = client.get("/profile", **kwargs)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert own.title in html
    assert victim.title not in html
    assert f'>{own.email}</span>' in html
    assert f'>{victim.email}</span>' not in html


@pytest.mark.parametrize("old_authenticated_flag", [False, True])
def test_requester_profile_requires_verified_binding(client, session, old_authenticated_flag):
    victim = _create_request(session, "profile-unverified")
    with client.session_transaction() as flask_session:
        flask_session["requester_email"] = victim.email
        flask_session["last_request_id"] = victim.id
        flask_session["requester_authenticated"] = old_authenticated_flag
    response = client.get("/profile", query_string={"requester_verified_email": victim.email})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/submit_request")
    assert victim.title not in response.get_data(as_text=True)


def test_requester_profile_new_submission_cannot_replace_verified_identity(client, session, monkeypatch):
    _reset_magic_link_rate_limits()
    _ensure_public_intake_route(session)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **kw: None)
    own = _create_request(session, "profile-before-submit")
    victim = _create_request(session, "profile-before-victim-submit")
    _consume_requester_link(client, session, own)

    preview, confirm = _submit_request_magic(client, email=victim.email, suffix="impersonation")
    assert preview.status_code == 200
    assert confirm.headers["Location"].endswith("/submit_request/check_email")
    with client.session_transaction() as flask_session:
        assert flask_session["requester_email"] == victim.email
        assert flask_session["requester_verified_email"] == own.email
    html = client.get("/profile").get_data(as_text=True)
    assert own.title in html
    assert victim.title not in html
    assert "Security request impersonation" not in html


def test_requester_profile_logout_revokes_verified_identity(client, session):
    own = _create_request(session, "profile-logout")
    _consume_requester_link(client, session, own)
    assert own.title in client.get("/profile").get_data(as_text=True)
    assert client.get("/requester/logout").status_code == 302
    with client.session_transaction() as flask_session:
        assert "requester_verified_email" not in flask_session
        assert "requester_authenticated" not in flask_session
    assert client.get("/profile").status_code == 302


def test_requester_profile_does_not_broaden_institutional_request_helpers(client, session):
    from werkzeug.exceptions import NotFound

    own = _create_request(session, "profile-helper-default")
    partner = Structure(name="Helper Partner", slug="profile-helper")
    session.add(partner)
    session.flush()
    routed = _create_request(session, "profile-helper-partner")
    routed.structure_id = partner.id
    routed.email = own.email
    session.commit()
    _consume_requester_link(client, session, routed)
    assert routed.title in client.get("/profile").get_data(as_text=True)
    with client.application.test_request_context("/profile"):
        assert {req.id for req in main_routes.scoped_requests_query().all()} == {own.id}
        assert main_routes.get_scoped_request_or_404(own.id).id == own.id
        with pytest.raises(NotFound):
            main_routes.get_scoped_request_or_404(routed.id)


@pytest.mark.parametrize("role", ["admin", "superadmin", "professional", "volunteer"])
def test_requester_profile_preserves_institutional_role_redirects(client, monkeypatch, role):
    from types import SimpleNamespace

    monkeypatch.setattr(
        main_routes, "current_user", SimpleNamespace(is_authenticated=True, role_canon=role)
    )
    response = client.get("/profile")
    assert response.status_code == 302
    expected = "/admin/requests" if role in {"admin", "superadmin"} else "/dashboard"
    assert response.headers["Location"].endswith(expected)


@pytest.mark.parametrize("token_state", ["missing", "expired", "used", "invalidated", "wrong_purpose"])
def test_requester_profile_rejected_link_cannot_establish_identity(client, session, token_state):
    req = _create_request(session, "profile-rejected")
    now = datetime.now(UTC)
    raw_token = "profile-rejected-token"
    if token_state != "missing":
        session.add(
            MagicLinkToken(
                purpose="unknown" if token_state == "wrong_purpose" else "request",
                email=req.email,
                request_id=req.id,
                token_hash=_sha256_hex(raw_token),
                expires_at=now + timedelta(minutes=-1 if token_state == "expired" else 15),
                used_at=now if token_state == "used" else None,
                invalidated_at=now if token_state == "invalidated" else None,
            )
        )
        session.commit()
    assert client.get(f"/auth/magic/{raw_token}").status_code == 200
    with client.session_transaction() as flask_session:
        assert not flask_session.get("requester_verified_email")
        assert not flask_session.get("requester_authenticated")
    assert client.get("/profile").status_code == 302


def test_requester_profile_legacy_link_establishes_verified_identity(client, session):
    req = _create_request(session, "profile-legacy")
    raw_token = "profile-legacy-token"
    req.requester_token_hash = _sha256_hex(raw_token)
    req.requester_token_created_at = datetime.now(UTC)
    session.commit()
    response = client.get(f"/auth/magic/{raw_token}", follow_redirects=True)
    assert response.status_code == 200
    assert req.title in response.get_data(as_text=True)
    with client.session_transaction() as flask_session:
        assert flask_session["requester_verified_email"] == req.email


def test_request_magic_link_smtp_failure_redacts_email_diagnostic(client, monkeypatch, caplog):
    from unittest.mock import mock_open

    from backend import mail_service

    caplog.set_level("INFO")
    monkeypatch.setenv("MAIL_MOCK", "0")
    for key, value in {
        "MAIL_SERVER": "smtp.test.local",
        "MAIL_PORT": 465,
        "MAIL_USERNAME": "sender@test.local",
        "MAIL_PASSWORD": "test-only-password",
        "MAIL_DEFAULT_SENDER": "sender@test.local",
        "MAIL_USE_SSL": True,
    }.items():
        monkeypatch.setitem(client.application.config, key, value)
    monkeypatch.setattr(mail_service, "_send_via_resend", lambda **kwargs: False)
    monkeypatch.setattr(
        mail_service, "render_template", lambda template, **context: context["magic_link_url"]
    )

    def fail_smtp(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", fail_smtp)
    email_log = mock_open()
    monkeypatch.setattr(mail_service, "open", email_log, raising=False)
    raw_token = "diagnostic-secret-magic-token"
    magic_url = f"https://helpchain.test/auth/magic/{raw_token}"
    with client.application.app_context():
        assert mail_service.send_notification_email(
            "diagnostic@test.local",
            "Confirm your request",
            "emails/magic_link.html",
            {"magic_link_url": magic_url},
            purpose="request_magic_link",
        ) is False

    email_log.assert_called_once_with("sent_emails.txt", "a", encoding="utf-8")
    diagnostic = "".join(call.args[0] for call in email_log().write.call_args_list)
    assert "[Sensitive email body redacted]" in diagnostic
    assert raw_token not in diagnostic + caplog.text
    assert magic_url not in diagnostic + caplog.text
