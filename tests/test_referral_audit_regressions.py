"""Referral boundary/failure checks using disposable fixture databases only."""

import re
from html import unescape

import pytest
from flask.testing import FlaskClient

from backend.models import AdminAuditEvent, CaseReferral, ReferralActivity, Request, db
from backend.helpchain_backend.src.routes import admin_referrals as routes
from tests.test_admin_partner_referrals import _admin, _login, _seed_referral_context, _send_referral


@pytest.fixture(autouse=True)
def fresh_request_app_context(monkeypatch):
    # db_schema keeps an outer app context alive. Real HTTP requests have fresh
    # g/current_user/tenant caches; preserve that isolation when switching users.
    original_open = FlaskClient.open

    def open_in_context(self, *args, **kwargs):
        with self.application.app_context():
            return original_open(self, *args, **kwargs)

    monkeypatch.setattr(FlaskClient, "open", open_in_context)


def _html(response):
    return unescape(response.get_data(as_text=True))


def test_structure_bound_superadmin_cannot_read_unrelated_referrals(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    scoped_superadmin = _admin("scoped_super_audit", ctx["c"].id, "superadmin")
    db.session.commit()
    _login(client, app, scoped_superadmin)
    assert client.get(f"/admin/referrals/{referral.id}").status_code == 403
    for path in ("/admin/referrals", "/admin/referrals/received", "/admin/referrals/sent"):
        response = client.get(path)
        assert response.status_code == 200
        assert referral.reason not in _html(response)
    response = client.get("/admin/referrals/partners")
    assert ctx["a"].name.encode() not in response.data
    assert ctx["b"].name.encode() not in response.data


def test_global_superadmin_retains_referral_visibility(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    _login(client, app, ctx["superadmin"])
    assert client.get(f"/admin/referrals/{referral.id}").status_code == 200
    assert referral.reason in _html(client.get("/admin/referrals"))


@pytest.mark.parametrize("failure", ["exception", "missing_tables"])
def test_acceptance_failure_rolls_back_and_can_retry(client, app, monkeypatch, failure):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    _login(client, app, ctx["admin_b"])
    original = routes._create_local_request_from_referral

    def broken(row):
        if failure == "missing_tables":
            return None
        original(row)
        raise RuntimeError("simulated conversion failure after flush")

    monkeypatch.setattr(routes, "_create_local_request_from_referral", broken)
    response = client.post(f"/admin/referrals/{referral.id}/accept")
    assert response.status_code == 303
    db.session.refresh(referral)
    assert referral.status == referral.operational_status == "sent"
    assert referral.accepted_at is None
    assert referral.accepted_by_admin_id is None
    assert Request.query.filter_by(structure_id=ctx["b"].id).count() == 0
    assert ReferralActivity.query.filter_by(referral_id=referral.id, action="accepted").count() == 0
    assert AdminAuditEvent.query.filter_by(target_id=referral.id, action="referral.accept").count() == 0
    monkeypatch.setattr(routes, "_create_local_request_from_referral", original)
    assert client.post(f"/admin/referrals/{referral.id}/accept").status_code == 303
    db.session.refresh(referral)
    assert referral.status == "accepted"
    assert Request.query.filter_by(structure_id=ctx["b"].id).count() == 1


def test_unchecked_summary_is_not_exposed_or_copied(client, app):
    ctx = _seed_referral_context()
    _login(client, app, ctx["admin_a"])
    response = client.post(
        f"/admin/requests/{ctx['request'].id}/refer",
        data={"to_structure_id": ctx["b"].id, "reason": "Only reason shared", "message": "SECRET-UNSHARED-SUMMARY"},
    )
    assert response.status_code == 303
    referral = CaseReferral.query.one()
    _login(client, app, ctx["admin_b"])
    assert b"SECRET-UNSHARED-SUMMARY" not in client.get(f"/admin/referrals/{referral.id}").data
    client.post(f"/admin/referrals/{referral.id}/accept")
    local = Request.query.filter_by(structure_id=ctx["b"].id).one()
    assert local.description == "Only reason shared"


def test_empty_explicit_summary_does_not_copy_live_source_description(client, app):
    ctx = _seed_referral_context()
    _login(client, app, ctx["admin_a"])
    client.post(
        f"/admin/requests/{ctx['request'].id}/refer",
        data={"to_structure_id": ctx["b"].id, "reason": "Reason only", "share_summary": "1"},
    )
    referral = CaseReferral.query.one()
    ctx["request"].description = "SECRET-ADDED-AFTER-SEND"
    db.session.commit()
    _login(client, app, ctx["admin_b"])
    client.post(f"/admin/referrals/{referral.id}/accept")
    local = Request.query.filter_by(structure_id=ctx["b"].id).one()
    assert local.description == "Reason only"


def test_existing_unshared_summary_is_hidden_without_rewriting_data(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    referral.shared_scope_json = {**referral.shared_scope_json, "share_summary": False}
    referral.message = "HISTORICAL-UNSHARED-SUMMARY"
    db.session.commit()
    _login(client, app, ctx["admin_b"])
    response = client.get(f"/admin/referrals/{referral.id}")
    assert b"HISTORICAL-UNSHARED-SUMMARY" not in response.data
    db.session.refresh(referral)
    assert referral.message == "HISTORICAL-UNSHARED-SUMMARY"


@pytest.mark.parametrize("terminal", ["refused", "cancelled", "completed"])
def test_terminal_public_note_is_immutable(client, app, terminal):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    if terminal == "cancelled":
        client.post(f"/admin/referrals/{referral.id}/cancel")
    else:
        _login(client, app, ctx["admin_b"])
        if terminal == "completed":
            client.post(f"/admin/referrals/{referral.id}/accept")
            client.post(f"/admin/referrals/{referral.id}/mark-completed")
        else:
            client.post(f"/admin/referrals/{referral.id}/refuse")
    db.session.refresh(referral)
    previous_note, previous_time = referral.public_status_note, referral.last_public_update_at
    previous_count = ReferralActivity.query.filter_by(referral_id=referral.id).count()
    _login(client, app, ctx["admin_b"])
    response = client.post(f"/admin/referrals/{referral.id}/public-note", data={"public_status_note": "Overwrite terminal"})
    assert response.status_code == 303
    db.session.refresh(referral)
    assert referral.status == terminal
    assert referral.public_status_note == previous_note
    assert referral.last_public_update_at == previous_time
    assert ReferralActivity.query.filter_by(referral_id=referral.id).count() == previous_count


@pytest.mark.parametrize("action", ["accept", "refuse", "cancel", "mark-in-progress", "mark-completed", "public-note"])
def test_unrelated_structure_cannot_mutate_by_direct_url(client, app, action):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    _login(client, app, ctx["admin_c"])
    response = client.post(f"/admin/referrals/{referral.id}/{action}", data={"public_status_note": "Forged"})
    assert response.status_code == 403
    db.session.refresh(referral)
    assert referral.status == "sent"
    assert ReferralActivity.query.filter_by(referral_id=referral.id).count() == 2


def test_source_and_target_spoofing_and_cross_tenant_request_are_rejected(client, app):
    ctx = _seed_referral_context()
    _login(client, app, ctx["admin_a"])
    path = f"/admin/requests/{ctx['request'].id}/refer"
    response = client.post(path, data={"source_structure_id": ctx["c"].id, "to_structure_id": ctx["b"].id, "reason": "Spoof probe"})
    assert response.status_code == 303
    row = CaseReferral.query.one()
    assert row.from_structure_id == ctx["a"].id
    for target in (ctx["c"].id, ctx["a"].id, 999999, "bad"):
        assert client.post(path, data={"to_structure_id": target, "reason": "Invalid target"}).status_code == 302
        assert CaseReferral.query.count() == 1
    _login(client, app, ctx["admin_b"])
    assert client.get(path).status_code == 404
    assert client.post(path, data={"to_structure_id": ctx["a"].id, "reason": "Forged source Request"}).status_code == 404


def test_incoming_outgoing_lists_exclude_unrelated_referral(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    for actor, incoming, outgoing in (("admin_a", False, True), ("admin_b", True, False), ("admin_c", False, False)):
        _login(client, app, ctx[actor])
        for direction, expected in (("received", incoming), ("sent", outgoing)):
            response = client.get(f"/admin/referrals/{direction}")
            assert response.status_code == 200
            assert (referral.reason in _html(response)) is expected


def test_sequential_repeats_and_invalid_transitions_preserve_state(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    _login(client, app, ctx["admin_b"])
    for action in ("mark-in-progress", "mark-completed"):
        client.post(f"/admin/referrals/{referral.id}/{action}")
        db.session.refresh(referral)
        assert referral.status == "sent"
    for action in ("accept", "mark-in-progress", "mark-completed"):
        for _ in range(2):
            client.post(f"/admin/referrals/{referral.id}/{action}")
    client.post(f"/admin/referrals/{referral.id}/accept")
    client.post(f"/admin/referrals/{referral.id}/refuse")
    client.post(f"/admin/referrals/{referral.id}/mark-in-progress")
    db.session.refresh(referral)
    assert referral.status == referral.operational_status == "completed"
    assert Request.query.filter_by(structure_id=ctx["b"].id).count() == 1
    for action in ("accepted", "in_progress", "completed"):
        assert ReferralActivity.query.filter_by(referral_id=referral.id, action=action).count() == 1
    _login(client, app, ctx["admin_a"])
    assert client.post(f"/admin/referrals/{referral.id}/cancel").status_code == 403
    for action in ("accept", "refuse", "mark-in-progress", "mark-completed", "public-note"):
        assert client.post(f"/admin/referrals/{referral.id}/{action}").status_code == 403


def test_referral_post_enforces_real_csrf_token(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    _login(client, app, ctx["admin_b"])
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get(f"/admin/referrals/{referral.id}")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    for payload in ({}, {"csrf_token": "invalid"}):
        assert client.post(f"/admin/referrals/{referral.id}/accept", data=payload).status_code == 400
    db.session.refresh(referral)
    assert referral.status == "received"
    assert client.post(f"/admin/referrals/{referral.id}/accept", data={"csrf_token": token}).status_code == 303
    db.session.refresh(referral)
    assert referral.status == "accepted"


def test_readonly_and_anonymous_cannot_mutate_referrals(client, app):
    ctx = _seed_referral_context()
    referral = _send_referral(client, app, ctx)
    readonly = _admin("readonly_audit", ctx["b"].id, "readonly")
    db.session.commit()
    _login(client, app, readonly)
    assert client.post(f"/admin/referrals/{referral.id}/accept").status_code in (403, 404)
    anonymous = app.test_client()
    for response in (anonymous.get(f"/admin/referrals/{referral.id}"), anonymous.post(f"/admin/referrals/{referral.id}/accept")):
        assert response.status_code in (302, 303, 401, 403, 404)
        if response.status_code in (302, 303):
            assert "login" in response.headers["Location"]
    db.session.refresh(referral)
    assert referral.status == "sent"
