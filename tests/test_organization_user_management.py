from datetime import timedelta

import pytest

from backend.models import AdminUser, Structure, db, utc_now
from backend.helpchain_backend.src.models.magic_link_token import MagicLinkToken
from tests.test_admin_team import _admin, _login


@pytest.fixture
def team(client, app):
    a = Structure(name="Management A", slug="management-a", status="active")
    b = Structure(name="Management B", slug="management-b", status="active")
    db.session.add_all([a, b])
    db.session.flush()
    owner = _admin("management_owner", a.id)
    member = _admin("management_member", a.id, "ops")
    outsider = _admin("management_outsider", b.id, "ops")
    db.session.commit()
    _login(client, app, owner)
    return owner, member, outsider


@pytest.mark.parametrize("action,data", [
    ("role", {"role": "admin"}),
    ("status", {"is_active": "0"}),
    ("status", {"is_active": "1"}),
    ("reset-access", {}),
])
def test_cross_tenant_member_mutations_denied(client, team, action, data, monkeypatch):
    owner, member, outsider = team
    def forbidden_mail(*args, **kwargs):
        pytest.fail("Cross-tenant mutation must not send mail")
    monkeypatch.setattr("backend.mail_service.send_notification_email", forbidden_mail)
    response = client.post(f"/admin/team/users/{outsider.id}/{action}",
                           data={**data, "structure_id": outsider.structure_id})
    assert response.status_code == 404
    db.session.expire_all()
    assert outsider.role == "ops"
    assert outsider.is_active
    assert MagicLinkToken.query.filter_by(purpose="admin_access_reset").count() == 0


@pytest.mark.parametrize("role", ["ops", "readonly", "superadmin"])
def test_non_org_admin_cannot_manage_members(client, app, team, role):
    owner, member, _ = team
    owner.role = role
    db.session.commit()
    _login(client, app, owner)
    assert client.get("/admin/team").status_code == 403
    for action, data in [("role", {"role": "admin"}),
                         ("status", {"is_active": "0"}), ("reset-access", {})]:
        assert client.post(f"/admin/team/users/{member.id}/{action}", data=data).status_code == 403
    assert client.post("/admin/team/invite", data={"email": "new@example.test", "role": "ops"}).status_code == 403


def test_own_member_roles_status_and_ui(client, team):
    owner, member, outsider = team
    page = client.get("/admin/team")
    assert f"/team/users/{member.id}/reset-access" in page.text
    assert outsider.email not in page.text
    assert 'href="/admin/team"' in page.text
    assert client.post(f"/admin/team/users/{member.id}/role", data={"role": "admin", "structure_id": outsider.structure_id}).status_code == 303
    db.session.expire_all()
    assert member.role == "admin"
    assert member.structure_id == owner.structure_id
    for status in ["0", "1"]:
        assert client.post(f"/admin/team/users/{member.id}/status", data={"is_active": status}).status_code == 303
        db.session.expire_all()
        assert member.is_active == (status == "1")
    assert client.post(f"/admin/team/users/{member.id}/role", data={"role": "superadmin"}).status_code == 400
    assert client.post(f"/admin/team/users/{owner.id}/role", data={"role": "ops"}).status_code == 409
    assert client.post(f"/admin/team/users/{owner.id}/status", data={"is_active": "0"}).status_code == 409


def test_two_active_org_admins_can_manage_each_other(client, team):
    owner, member, _ = team
    member.role = "admin"
    member.is_active = True
    db.session.commit()

    response = client.post(
        f"/admin/team/users/{member.id}/role",
        data={"role": "ops"},
    )
    assert response.status_code == 303
    db.session.expire_all()
    assert member.role == "ops"
    assert owner.role == "admin"
    assert owner.is_active

    member.role = "admin"
    member.is_active = True
    db.session.commit()

    response = client.post(
        f"/admin/team/users/{member.id}/status",
        data={"is_active": "0"},
    )
    assert response.status_code == 303
    db.session.expire_all()
    assert not member.is_active
    assert owner.role == "admin"
    assert owner.is_active


def _issue(client, member, monkeypatch):
    captured = {}
    def send(recipient, subject, template, context, **kwargs):
        captured.update(recipient=recipient, **context)
        return True
    monkeypatch.setattr("backend.mail_service.send_notification_email", send)
    response = client.post(f"/admin/team/users/{member.id}/reset-access")
    assert response.status_code == 303
    assert captured["recipient"] == member.email
    link = captured["magic_link_url"]
    assert "/team/reset-access#" in link
    raw = link.split("#", 1)[1]
    assert raw not in response.text
    return raw


def _consume(client, raw, password="NewSecurePass123"):
    return client.post("/team/reset-access", data={
        "token": raw, "password": password, "confirm_password": password,
    })


def test_reset_single_use_password_policy_and_no_auth_bypass(client, team, monkeypatch, caplog):
    _, member, _ = team
    original = member.password_hash
    raw = _issue(client, member, monkeypatch)
    assert _consume(client, raw, "weak").status_code == 400
    db.session.expire_all()
    assert member.password_hash == original
    assert _consume(client, raw).status_code == 303
    db.session.expire_all()
    assert member.check_password("NewSecurePass123")
    assert member.role == "ops"
    assert _consume(client, raw).status_code == 400
    assert raw not in caplog.text
    with client.session_transaction() as sess:
        assert not sess.get("admin_logged_in")


@pytest.mark.parametrize("change", ["expired", "moved", "disabled", "role", "password", "issuer_disabled", "tampered", "rotated"])
def test_reset_rejects_changed_or_expired_credentials(client, team, monkeypatch, change):
    owner, member, outsider = team
    raw = _issue(client, member, monkeypatch)
    if change == "expired":
        MagicLinkToken.query.filter_by(purpose="admin_access_reset").one().expires_at = utc_now() - timedelta(seconds=1)
    elif change == "moved":
        member.structure_id = outsider.structure_id
    elif change == "disabled":
        client.post(f"/admin/team/users/{member.id}/status", data={"is_active": "0"})
        client.post(f"/admin/team/users/{member.id}/status", data={"is_active": "1"})
    elif change == "role":
        client.post(f"/admin/team/users/{member.id}/role", data={"role": "admin"})
    elif change == "password":
        member.set_password("ChangedPass123")
    elif change == "issuer_disabled":
        owner.is_active = False
    elif change == "tampered":
        raw += "tampered"
    elif change == "rotated":
        _issue(client, member, monkeypatch)
    db.session.commit()
    old_hash = member.password_hash
    assert _consume(client, raw).status_code == 400
    db.session.expire_all()
    assert member.password_hash == old_hash


def test_failed_reset_delivery_invalidates_even_if_mail_commits(client, team, monkeypatch, caplog):
    _, member, _ = team
    captured = {}
    def send(*args, **kwargs):
        captured["raw"] = args[3]["magic_link_url"].split("#", 1)[1]
        db.session.commit()  # Real mail telemetry commits the shared session.
        raise RuntimeError(captured["raw"])
    monkeypatch.setattr("backend.mail_service.send_notification_email", send)
    assert client.post(f"/admin/team/users/{member.id}/reset-access").status_code == 303
    assert _consume(client, captured["raw"]).status_code == 400
    assert captured["raw"] not in caplog.text


def test_disabled_admin_session_cannot_manage_team(client, team):
    owner, member, _ = team
    owner.is_active = False
    db.session.commit()
    assert client.post(f"/admin/team/users/{member.id}/role", data={"role": "admin"}).status_code in {403, 404}


def test_disabled_operator_cannot_login_or_reuse_session(client, app, team):
    _, member, _ = team
    member.set_password("OperatorPass123")
    member.is_active = False
    db.session.commit()
    _login(client, app, member)
    assert client.get("/admin/operator").status_code in {302, 303, 403, 404}
    assert client.get("/ops").status_code in {302, 303, 403, 404}
    with client.session_transaction() as sess:
        sess.clear()
    response = client.post("/admin/login", data={"username": member.username, "password": "OperatorPass123"})
    assert response.status_code in {302, 303}
    with client.session_transaction() as sess:
        assert not sess.get("admin_logged_in")
        assert not sess.get("pending_admin_user_id")


def test_csrf_required_for_management_and_reset(client, app, team):
    _, member, _ = team
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/admin/team/users/{member.id}/status", data={"is_active": "0"}).status_code == 400
    assert _consume(client, "fake").status_code == 400
    page = client.get("/team/reset-access")
    assert page.status_code == 200
    assert 'name="csrf_token"' in page.text
    assert page.headers["Cache-Control"] == "no-store"
    assert client.get("/static/js/pages/admin_access_reset.js").status_code == 200


def test_reset_uses_configured_public_origin(client, app, team, monkeypatch):
    _, member, _ = team
    app.config["PUBLIC_BASE_URL"] = "https://trusted.example"
    def send(recipient, subject, template, context, **kwargs):
        assert context["magic_link_url"].startswith("https://trusted.example/team/reset-access#")
        return True
    monkeypatch.setattr("backend.mail_service.send_notification_email", send)
    assert client.post(f"/admin/team/users/{member.id}/reset-access").status_code == 303


def test_legacy_user_management_cannot_bypass_tenant_rules(client, app, team):
    owner, member, _ = team
    for role in ["ops", "admin", "superadmin"]:
        owner.role = role
        db.session.commit()
        _login(client, app, owner)
        for path in ["/admin/roles/", "/admin/roles/users/create", "/admin/roles/users/1/roles"]:
            assert client.get(path).status_code == 403
        assert client.post("/admin/roles/users/1/toggle").status_code == 403
    assert client.post(f"/admin/roles/{member.id}/role", data={"role": "superadmin"}).status_code == 403


def test_reset_access_preserves_same_origin_referrer(client):
    response = client.get("/team/reset-access")

    assert response.status_code == 200
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert '<meta name="referrer" content="no-referrer">' not in response.text
