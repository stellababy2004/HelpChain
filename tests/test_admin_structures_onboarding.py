import pytest
from contextlib import contextmanager
import re

from sqlalchemy import event
from bs4 import BeautifulSoup
from flask import g

pytestmark = pytest.mark.shared_platform


def _pending_bootstrap(session, structure, admin, email="cancel-first@test.local"):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        create_admin_team_invitation,
    )

    invitation, token = create_admin_team_invitation(
        structure_id=structure.id, invited_by_admin_id=admin.id, email=email, role="admin"
    )
    session.commit()
    return invitation, token


def _cancel_url(structure, invitation):
    return f"/admin/structures/{structure.id}/bootstrap-admin/{invitation.id}/revoke"


def test_bootstrap_cancel_and_reinvite(client, session, monkeypatch):
    from backend.models import AdminAuditEvent, AdminUserInvitation

    structure = _make_structure(session, name="Cancel First", slug="cancel-first")
    other = _make_structure(session, name="Other First", slug="other-first")
    admin = _make_admin(session, username="cancel_global", email="cancel-global@test.local", role="superadmin")
    invitation, token = _pending_bootstrap(session, structure, admin)
    protected, protected_token = _pending_bootstrap(session, other, admin, "other-first@test.local")
    original_hash = invitation.token_hash
    _login_admin(client, admin)
    panel = BeautifulSoup(client.get(f"/admin/structures/{structure.id}").data, "html.parser").select_one("#first-admin-bootstrap")
    assert "Invitation en cours" in panel.get_text()
    button = panel.select_one('[data-action="confirmSubmit"]')
    assert button.get_text(strip=True) == "Annuler l’invitation"
    assert button["type"] == "button"
    assert button["data-confirm"] == "Êtes-vous sûr de vouloir annuler cette invitation ?"
    assert button.find_parent("form")["action"] == _cancel_url(structure, invitation)
    assert button.find_parent("form").select_one('[name="csrf_token"]') is not None
    assert client.post(_cancel_url(structure, invitation)).status_code == 303
    session.refresh(invitation)
    session.refresh(protected)
    assert invitation.revoked_at is not None
    assert invitation.accepted_at is None
    assert invitation.token_hash == original_hash
    assert protected.revoked_at is None
    assert client.get(f"/team/invitation/{protected_token}").status_code == 200
    assert client.get(f"/team/invitation/{token}").status_code == 400
    assert client.post(f"/team/invitation/{token}", data={"password": "StrongPassword123!", "confirm_password": "StrongPassword123!"}).status_code == 400
    panel = BeautifulSoup(client.get(f"/admin/structures/{structure.id}").data, "html.parser").select_one("#first-admin-bootstrap")
    assert panel.select_one('[name="email"]') is not None
    assert "Inviter le premier administrateur" in panel.get_text()
    assert "Annuler l’invitation" not in panel.get_text()
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **kw: True)
    assert client.post(f"/admin/structures/{structure.id}/bootstrap-admin", data={"email": "replacement@test.local"}).status_code == 303
    replacement = AdminUserInvitation.query.filter_by(structure_id=structure.id, revoked_at=None).one()
    assert replacement.id != invitation.id
    # Replaying the old form must leave the replacement pending.
    assert client.post(_cancel_url(structure, invitation)).status_code == 303
    session.refresh(replacement)
    assert replacement.revoked_at is None
    assert AdminUserInvitation.query.filter_by(structure_id=structure.id).count() == 2
    audits = AdminAuditEvent.query.filter_by(action="ADMIN_TEAM_INVITATION_REVOKED", target_id=invitation.id).all()
    assert len(audits) == 1
    assert audits[0].payload["structure_id"] == structure.id


@pytest.mark.parametrize("role,scoped", [("superadmin", True), ("admin", True), ("admin", False), ("ops", False), ("readonly", False)])
def test_bootstrap_cancel_requires_global_superadmin(client, session, role, scoped):
    own = _make_structure(session, name="Own Cancel", slug="own-cancel")
    other = _make_structure(session, name="Foreign Cancel", slug="foreign-cancel")
    admin = _make_admin(session, username="cancel_denied", email="cancel-denied@test.local", role=role, structure_id=own.id if scoped else None)
    invitation, _ = _pending_bootstrap(session, other, admin)
    _login_admin(client, admin)
    assert client.post(_cancel_url(other, invitation)).status_code == 403
    session.refresh(invitation)
    assert invitation.revoked_at is None


def test_bootstrap_cancel_scoped_to_invitation_and_post(client, session, app):
    own = _make_structure(session, name="Cancel Scope", slug="cancel-scope")
    other = _make_structure(session, name="Cancel Foreign", slug="cancel-foreign")
    admin = _make_admin(session, username="cancel_scope", email="cancel-scope@test.local", role="superadmin")
    invitation, _ = _pending_bootstrap(session, other, admin)
    assert client.post(_cancel_url(other, invitation)).status_code in (302, 303)
    _login_admin(client, admin)
    assert client.post(_cancel_url(own, invitation)).status_code == 404
    assert client.get(_cancel_url(other, invitation)).status_code == 405
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(_cancel_url(other, invitation)).status_code == 400
    session.refresh(invitation)
    assert invitation.revoked_at is None


@pytest.mark.parametrize("state", ["accepted", "expired", "ops"])
def test_bootstrap_cancel_only_pending_admin_invitation(client, session, state):
    from datetime import timedelta
    from backend.models import utc_now

    structure = _make_structure(session, name="Cancel State", slug="cancel-state")
    admin = _make_admin(session, username="cancel_state", email="cancel-state@test.local", role="superadmin")
    invitation, _ = _pending_bootstrap(session, structure, admin)
    if state == "accepted":
        invitation.accepted_at = utc_now()
    elif state == "expired":
        invitation.expires_at = utc_now() - timedelta(seconds=1)
    else:
        invitation.role = "ops"
    session.commit()
    _login_admin(client, admin)
    assert client.post(_cancel_url(structure, invitation)).status_code == (404 if state == "ops" else 303)
    session.refresh(invitation)
    assert invitation.revoked_at is None


@pytest.mark.parametrize("winner", ["revoked_at", "accepted_at"])
def test_bootstrap_accept_rechecks_state_after_token_read(client, session, monkeypatch, winner):
    from backend.models import AdminUser, AdminUserInvitation, utc_now
    from backend.helpchain_backend.src.services import admin_team_invitations as service

    structure = _make_structure(session, name="Cancel Race", slug="cancel-race")
    admin = _make_admin(session, username="cancel_race", email="cancel-race@test.local", role="superadmin")
    invitation, token = _pending_bootstrap(session, structure, admin)
    original_get = service.get_admin_team_invitation

    def read_then_transition(raw_token):
        stale = original_get(raw_token)
        # Simulate the winning write after validation, keeping the ORM object stale.
        AdminUserInvitation.query.filter_by(id=stale.id).update(
            {getattr(AdminUserInvitation, winner): utc_now()}, synchronize_session=False
        )
        return stale

    monkeypatch.setattr(service, "get_admin_team_invitation", read_then_transition)
    with pytest.raises(service.InvitationInvalid):
        service.accept_admin_team_invitation(raw_token=token, password="StrongPassword123!")
    assert AdminUser.query.filter_by(email=invitation.email).count() == 0
    session.rollback()


@contextmanager
def _count_select_queries(app):
    from backend.extensions import db

    counts = {"select": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if str(statement or "").lstrip().lower().startswith("select"):
            counts["select"] += 1

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def _login_admin(client, admin_user):
    for key in ("_current_admin_actor", "_session_admin_actor", "_bearer_admin_actor"):
        g.pop(key, None)
    with client.session_transaction() as s:
        s.clear()
        s["_user_id"] = str(admin_user.id)
        s["_fresh"] = True
        s["user_id"] = admin_user.id
        s["role"] = admin_user.role
        s["is_authenticated"] = True
        s["is_admin"] = True
        s["admin_logged_in"] = True
        s["admin_id"] = admin_user.id
        s["admin_user_id"] = admin_user.id
        s["mfa_ok"] = True
        s["mfa_ok_until"] = "2099-01-01T00:00:00+00:00"
        s["admin_mfa_last_verified"] = 4102444800
        s["admin_mfa_user_id"] = admin_user.id


def _make_admin(session, *, username, email, role="admin", structure_id=None):
    from backend.models import AdminUser

    admin = AdminUser(
        username=username,
        email=email,
        password_hash="x",
        role=role,
        is_active=True,
        structure_id=structure_id,
    )
    session.add(admin)
    session.commit()
    return admin


def _make_structure(session, *, name, slug):
    from backend.models import Structure

    row = Structure(name=name, slug=slug)
    session.add(row)
    session.commit()
    return row


def _make_user(session, *, username, email):
    from backend.models import User

    user = User(username=username, email=email, password_hash="x", role="requester")
    session.add(user)
    session.commit()
    return user


def _make_request(session, *, title, user_id, structure_id):
    from backend.models import Request

    req = Request(
        title=title,
        description="Test",
        category="general",
        user_id=user_id,
        structure_id=structure_id,
    )
    session.add(req)
    session.commit()
    return req


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_structures_list_requires_global_admin(client):
    resp = client.get("/admin/structures", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/admin/login" in (resp.headers.get("Location") or "")


def test_structures_list_accessible_for_global_admin(client, session):
    admin = _make_admin(
        session, username="global_admin", email="global_admin@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.get("/admin/structures", follow_redirects=False)
    assert resp.status_code == 200


def test_structure_create_success(client, session):
    admin = _make_admin(
        session, username="creator_admin", email="creator_admin@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.post(
        "/admin/structures/new",
        data={"name": "Structure A", "slug": "structure-a"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from backend.models import Structure

    created = Structure.query.filter_by(slug="structure-a").first()
    assert created is not None
    assert created.name == "Structure A"


def test_structure_create_accepts_valid_organization_type(client, session):
    admin = _make_admin(
        session, username="creator_valid_type", email="creator_valid_type@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.post(
        "/admin/structures/new",
        data={
            "name": "CCAS Valid Type",
            "slug": "ccas-valid-type",
            "organization_type": "ccas",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from backend.models import Structure

    created = Structure.query.filter_by(slug="ccas-valid-type").first()
    assert created is not None
    assert created.organization_type == "ccas"


def test_structure_create_rejects_invalid_organization_type(client, session):
    admin = _make_admin(
        session,
        username="creator_invalid_type",
        email="creator_invalid_type@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    resp = client.post(
        "/admin/structures/new",
        data={
            "name": "Invalid Type",
            "slug": "invalid-type",
            "organization_type": "invented_agency",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400

    from backend.models import Structure

    assert Structure.query.filter_by(slug="invalid-type").first() is None


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "slug": "missing-name"},
        {"name": "Missing Slug", "slug": ""},
        {"name": "", "slug": ""},
    ],
)
def test_structure_create_missing_fields(client, session, payload):
    admin = _make_admin(
        session, username="creator_missing", email="creator_missing@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.post("/admin/structures/new", data=payload, follow_redirects=False)
    assert resp.status_code == 400


def test_structure_create_duplicate_slug(client, session):
    _make_structure(session, name="Existing", slug="dup-slug")
    admin = _make_admin(
        session, username="creator_dup", email="creator_dup@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.post(
        "/admin/structures/new",
        data={"name": "Other", "slug": "dup-slug"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_structure_detail_loads(client, session):
    st = _make_structure(session, name="Detail", slug="detail")
    admin = _make_admin(
        session, username="detail_admin", email="detail_admin@test.local", role="superadmin"
    )
    _login_admin(client, admin)
    resp = client.get(f"/admin/structures/{st.id}", follow_redirects=False)
    assert resp.status_code == 200


def test_global_superadmin_sees_first_admin_bootstrap_form(client, session):
    st = _make_structure(session, name="Bootstrap Empty", slug="bootstrap-empty")
    admin = _make_admin(
        session,
        username="bootstrap_global_admin",
        email="bootstrap-global@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}", follow_redirects=False)

    assert resp.status_code == 200
    panel = BeautifulSoup(resp.data, "html.parser").select_one("#first-admin-bootstrap")
    assert panel is not None
    assert "Premier administrateur" in panel.get_text()
    assert "Inviter le premier administrateur" in panel.get_text()
    assert panel.select_one("form")["action"].endswith(
        f"/admin/structures/{st.id}/bootstrap-admin"
    )


@pytest.mark.parametrize("role", ["admin", "ops"])
def test_non_global_admins_cannot_bootstrap_first_admin(client, session, role):
    target = _make_structure(session, name=f"Bootstrap Denied {role}", slug=f"bootstrap-denied-{role}")
    own = _make_structure(session, name=f"Bootstrap Own {role}", slug=f"bootstrap-own-{role}")
    actor = _make_admin(
        session,
        username=f"bootstrap_denied_{role}",
        email=f"bootstrap-denied-{role}@test.local",
        role=role,
        structure_id=own.id,
    )
    _login_admin(client, actor)

    resp = client.post(
        f"/admin/structures/{target.id}/bootstrap-admin",
        data={"email": f"first-{role}@test.local"},
        follow_redirects=False,
    )

    assert resp.status_code == 403

    from backend.models import AdminUserInvitation

    assert AdminUserInvitation.query.filter_by(structure_id=target.id).count() == 0


def test_unauthenticated_cannot_bootstrap_first_admin(client, session):
    st = _make_structure(session, name="Bootstrap Anonymous", slug="bootstrap-anonymous")

    resp = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "anonymous-bootstrap@test.local"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert "/admin/login" in (resp.headers.get("Location") or "")


def test_bootstrap_creates_admin_invitation_for_url_structure_and_admin_role(
    client, session, monkeypatch
):
    from backend.models import AdminUserInvitation

    target = _make_structure(session, name="Bootstrap Target", slug="bootstrap-target")
    other = _make_structure(session, name="Bootstrap Other", slug="bootstrap-other")
    admin = _make_admin(
        session,
        username="bootstrap_creator",
        email="bootstrap-creator@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    captured = {}

    def fake_send(recipient, subject, template, context, **kwargs):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["template"] = template
        captured["context"] = dict(context)
        captured["kwargs"] = dict(kwargs)
        return True

    monkeypatch.setattr("backend.mail_service.send_notification_email", fake_send)

    resp = client.post(
        f"/admin/structures/{target.id}/bootstrap-admin",
        data={
            "email": "First.Admin@Example.TEST",
            "role": "superadmin",
            "structure_id": str(other.id),
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    invitation = AdminUserInvitation.query.filter_by(
        email="first.admin@example.test"
    ).one()
    assert invitation.structure_id == target.id
    assert invitation.structure_id != other.id
    assert invitation.role == "admin"
    assert invitation.invited_by_admin_id == admin.id
    assert len(invitation.token_hash) == 64
    raw_token = captured["context"]["invitation_url"].rsplit("/", 1)[-1]
    assert raw_token
    assert raw_token not in invitation.token_hash
    assert captured["recipient"] == "first.admin@example.test"
    assert captured["template"] == "emails/admin_team_invitation.html"
    assert captured["kwargs"]["purpose"] == "admin_team_invitation"
    assert captured["kwargs"]["structure_id"] == target.id


def test_bootstrap_token_and_url_are_not_logged(client, session, monkeypatch, caplog):
    from backend.models import AdminUserInvitation

    st = _make_structure(session, name="Bootstrap Logs", slug="bootstrap-logs")
    admin = _make_admin(
        session,
        username="bootstrap_log_admin",
        email="bootstrap-log-admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    captured = {}

    def fake_send(recipient, subject, template, context, **kwargs):
        captured["url"] = context["invitation_url"]
        return True

    monkeypatch.setattr("backend.mail_service.send_notification_email", fake_send)

    resp = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-logs@test.local"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    invitation = AdminUserInvitation.query.filter_by(email="bootstrap-logs@test.local").one()
    raw_token = captured["url"].rsplit("/", 1)[-1]
    logs = caplog.text
    assert raw_token not in logs
    assert captured["url"] not in logs
    assert raw_token not in invitation.token_hash


def test_bootstrap_acceptance_creates_structure_admin_who_can_manage_team(
    client, session, monkeypatch
):
    from backend.models import AdminUser, AdminUserInvitation

    st = _make_structure(session, name="Bootstrap Accept", slug="bootstrap-accept")
    global_admin = _make_admin(
        session,
        username="bootstrap_accept_global",
        email="bootstrap-accept-global@test.local",
        role="superadmin",
    )
    _login_admin(client, global_admin)
    captured = {}
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda _recipient, _subject, _template, context, **_kwargs: captured.setdefault(
            "url", context["invitation_url"]
        )
        or True,
    )

    client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "accepted-bootstrap@test.local"},
        follow_redirects=False,
    )
    raw_token = captured["url"].rsplit("/", 1)[-1]

    accept = client.post(
        f"/team/invitation/{raw_token}",
        data={"password": "SecurePass123", "confirm_password": "SecurePass123"},
        follow_redirects=False,
    )

    assert accept.status_code == 303
    created = AdminUser.query.filter_by(email="accepted-bootstrap@test.local").one()
    assert created.role == "admin"
    assert created.structure_id == st.id
    invitation = AdminUserInvitation.query.filter_by(
        email="accepted-bootstrap@test.local"
    ).one()
    assert invitation.accepted_at is not None

    client = client.application.test_client()
    _login_admin(client, created)
    team = client.get("/admin/team", follow_redirects=False)
    assert team.status_code == 200


def test_bootstrap_refused_after_user_or_pending_invitation(client, session, monkeypatch):
    from backend.models import AdminUserInvitation, utc_now

    st = _make_structure(session, name="Bootstrap Once", slug="bootstrap-once")
    global_admin = _make_admin(
        session,
        username="bootstrap_once_global",
        email="bootstrap-once-global@test.local",
        role="superadmin",
    )
    _login_admin(client, global_admin)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)

    first = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "first-bootstrap-once@test.local"},
        follow_redirects=False,
    )
    second = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "second-bootstrap-once@test.local"},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert second.status_code == 303
    assert AdminUserInvitation.query.filter_by(structure_id=st.id).count() == 1

    invite = AdminUserInvitation.query.filter_by(structure_id=st.id).one()
    invite.revoked_at = utc_now()
    _make_admin(
        session,
        username="bootstrap_existing_tenant_admin",
        email="bootstrap-existing-tenant-admin@test.local",
        role="admin",
        structure_id=st.id,
    )

    third = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "third-bootstrap-once@test.local"},
        follow_redirects=False,
    )

    assert third.status_code == 303
    assert AdminUserInvitation.query.filter_by(structure_id=st.id).count() == 1


def test_bootstrap_rejects_existing_user_and_duplicate_pending_email(
    client, session, monkeypatch
):
    from backend.models import AdminUserInvitation

    st = _make_structure(session, name="Bootstrap Duplicates", slug="bootstrap-duplicates")
    global_admin = _make_admin(
        session,
        username="bootstrap_dupes_global",
        email="bootstrap-dupes-global@test.local",
        role="superadmin",
    )
    existing = _make_admin(
        session,
        username="bootstrap_dupes_existing",
        email="bootstrap-dupes-existing@test.local",
        role="admin",
        structure_id=None,
    )
    _login_admin(client, global_admin)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)

    existing_resp = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": existing.email},
        follow_redirects=False,
    )

    assert existing_resp.status_code == 303
    assert AdminUserInvitation.query.filter_by(structure_id=st.id).count() == 0

    first = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-pending-dupe@test.local"},
        follow_redirects=False,
    )
    second = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-pending-dupe@test.local"},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert second.status_code == 303
    assert AdminUserInvitation.query.filter_by(structure_id=st.id).count() == 1


def test_bootstrap_email_failure_rolls_back_and_does_not_audit_success(
    client, session, monkeypatch
):
    from backend.models import AdminAuditEvent, AdminUserInvitation

    st = _make_structure(session, name="Bootstrap Mail Fail", slug="bootstrap-mail-fail")
    global_admin = _make_admin(
        session,
        username="bootstrap_mail_fail_global",
        email="bootstrap-mail-fail-global@test.local",
        role="superadmin",
    )
    _login_admin(client, global_admin)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: False)

    resp = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-mail-fail@test.local"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert AdminUserInvitation.query.filter_by(structure_id=st.id).count() == 0
    assert (
        AdminAuditEvent.query.filter_by(
            action="ADMIN_TEAM_BOOTSTRAP_INVITATION_CREATED"
        ).count()
        == 0
    )


def test_bootstrap_success_creates_audit_event(client, session, monkeypatch):
    from backend.models import AdminAuditEvent

    st = _make_structure(session, name="Bootstrap Audit", slug="bootstrap-audit")
    global_admin = _make_admin(
        session,
        username="bootstrap_audit_global",
        email="bootstrap-audit-global@test.local",
        role="superadmin",
    )
    _login_admin(client, global_admin)
    monkeypatch.setattr("backend.mail_service.send_notification_email", lambda *a, **k: True)

    resp = client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-audit-target@test.local"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    event = AdminAuditEvent.query.filter_by(
        action="ADMIN_TEAM_BOOTSTRAP_INVITATION_CREATED"
    ).one()
    assert event.target_type == "AdminUserInvitation"
    assert event.payload["actor_admin_id"] == global_admin.id
    assert event.payload["structure_id"] == st.id
    assert event.payload["invited_email"] == "bootstrap-audit-target@test.local"
    assert event.payload["role"] == "admin"


def test_bootstrap_preserves_team_access_boundaries(client, session, monkeypatch):
    from backend.models import AdminUser

    st = _make_structure(session, name="Bootstrap Boundary", slug="bootstrap-boundary")
    other = _make_structure(session, name="Bootstrap Boundary Other", slug="bootstrap-boundary-other")
    global_admin = _make_admin(
        session,
        username="bootstrap_boundary_global",
        email="bootstrap-boundary-global@test.local",
        role="superadmin",
    )
    other_admin = _make_admin(
        session,
        username="bootstrap_boundary_other_admin",
        email="bootstrap-boundary-other-admin@test.local",
        role="admin",
        structure_id=other.id,
    )
    _login_admin(client, global_admin)
    captured = {}
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda _recipient, _subject, _template, context, **_kwargs: captured.setdefault(
            "url", context["invitation_url"]
        )
        or True,
    )

    assert client.get("/admin/team", follow_redirects=False).status_code == 403

    client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "bootstrap-boundary-admin@test.local"},
        follow_redirects=False,
    )
    token = captured["url"].rsplit("/", 1)[-1]
    client.post(
        f"/team/invitation/{token}",
        data={"password": "SecurePass123", "confirm_password": "SecurePass123"},
        follow_redirects=False,
    )
    created = AdminUser.query.filter_by(email="bootstrap-boundary-admin@test.local").one()

    tenant_client = client.application.test_client()
    _login_admin(tenant_client, created)
    assert tenant_client.get("/admin/team", follow_redirects=False).status_code == 200

    other_client = client.application.test_client()
    _login_admin(other_client, other_admin)
    cross_tenant = other_client.post(
        f"/admin/structures/{st.id}/bootstrap-admin",
        data={"email": "cross-tenant-bootstrap@test.local"},
        follow_redirects=False,
    )
    assert cross_tenant.status_code == 403


@pytest.mark.parametrize("configuration", ["empty", "coverage_only", "ready"])
def test_structure_page_shows_public_intake_readiness(client, session, configuration):
    from backend.models import StructureCoverageArea, StructureService

    st = _make_structure(session, name="Public Intake UI", slug="public-intake-ui")
    admin = _make_admin(
        session, username="public_intake_ui", email="public_intake_ui@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    if configuration != "empty":
        st.status = "active"
        session.add(StructureCoverageArea(
            structure_id=st.id, area_type="city", name="Paris",
            postal_code="75001", is_active=True,
        ))
    if configuration == "ready":
        session.add(StructureService(
            structure_id=st.id, name="Aide alimentaire", code="food", is_active=True,
        ))
    session.commit()

    response = client.get(f"/admin/structures/{st.id}")

    assert response.status_code == 200
    panel = BeautifulSoup(response.data, "html.parser").select_one("#public-intake-readiness")
    assert panel is not None
    assert "Réception des demandes publiques" in panel.get_text()
    if configuration == "ready":
        assert panel.select_one(".badge").get_text(strip=True) == "Prête"
        assert not panel.select("li")
    else:
        assert panel.select_one(".badge").get_text(strip=True) == "Non configurée"
        guidance = [item.get_text(strip=True) for item in panel.select("li")]
        expected = ["Ajouter au moins un service actif pour les demandes publiques."]
        if configuration == "empty":
            expected = [
                "Activer la structure dans le workspace.",
                "Ajouter au moins une zone de couverture active.",
            ] + expected
        assert guidance == expected


def test_structure_operational_intelligence_endpoint(client, session):
    st = _make_structure(session, name="Operational Detail", slug="operational-detail")
    admin = _make_admin(
        session,
        username="ops_intel_admin",
        email="ops_intel_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(
        f"/admin/structures/{st.id}/operational-intelligence",
        follow_redirects=False,
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["profile"]["name"] == "Operational Detail"
    assert payload["capacity"]["active_cases"]["source_tables"] == ["requests"]
    assert payload["health"]["display"] == "Donnée indisponible"


def test_structure_operational_intelligence_blocks_foreign_structure(client, session):
    own = _make_structure(session, name="Own Tenant", slug="own-tenant")
    foreign = _make_structure(session, name="Foreign Tenant", slug="foreign-tenant")
    admin = _make_admin(
        session,
        username="tenant_ops_intel_admin",
        email="tenant_ops_intel_admin@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.get(
        f"/admin/structures/{foreign.id}/operational-intelligence",
        follow_redirects=False,
    )

    assert resp.status_code == 403


def test_empty_intervenant_availability_does_not_count_as_available(client, session):
    from backend.models import Intervenant

    st = _make_structure(session, name="Availability Truth", slug="availability-truth")
    admin = _make_admin(
        session,
        username="availability_admin",
        email="availability_admin@test.local",
        role="superadmin",
    )
    session.add(
        Intervenant(
            structure_id=st.id,
            name="Unknown Availability",
            actor_type="social_worker",
            availability="",
            is_active=True,
        )
    )
    session.commit()
    _login_admin(client, admin)

    resp = client.get(
        f"/admin/structures/{st.id}/operational-intelligence",
        follow_redirects=False,
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["capacity"]["professionals"]["value"] == 1
    assert payload["capacity"]["available_professionals"]["value"] == 0


def test_empty_service_availability_does_not_increase_available_capacity(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Service Availability", slug="service-availability")
    admin = _make_admin(
        session,
        username="service_availability_admin",
        email="service_availability_admin@test.local",
        role="superadmin",
    )
    session.add(
        StructureService(
            structure_id=st.id,
            code="unknown-availability",
            name="Disponibilité inconnue",
            category="social_support",
            capacity=12,
            availability="",
            is_active=True,
        )
    )
    session.commit()
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["capacity"]["maximum_capacity"]["value"] is None
    assert payload["capacity"]["available_capacity"]["value"] is None


def test_structures_index_query_count_is_not_per_structure(client, session, app):
    admin = _make_admin(
        session,
        username="query_count_admin",
        email="query_count_admin@test.local",
        role="superadmin",
    )
    for index in range(8):
        st = _make_structure(session, name=f"Query Org {index}", slug=f"query-org-{index}")
        user = _make_user(session, username=f"query-user-{index}", email=f"query-user-{index}@test.local")
        _make_request(session, title=f"Query Request {index}", user_id=user.id, structure_id=st.id)
    _login_admin(client, admin)

    with _count_select_queries(app) as counts:
        resp = client.get("/admin/structures", follow_redirects=False)

    assert resp.status_code == 200
    assert counts["select"] <= 12


def test_structure_detail_query_count_is_materially_reduced(client, session, app):
    st = _make_structure(session, name="Detail Query Count", slug="detail-query-count")
    user = _make_user(session, username="detail-query-user", email="detail-query-user@test.local")
    _make_request(session, title="Detail Query Request", user_id=user.id, structure_id=st.id)
    admin = _make_admin(
        session,
        username="detail_query_admin",
        email="detail_query_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    with _count_select_queries(app) as counts:
        resp = client.get(f"/admin/structures/{st.id}", follow_redirects=False)

    assert resp.status_code == 200
    assert counts["select"] <= 30


def test_structure_service_form_offers_public_intake_codes(client, session):
    from backend.models import StructureService
    from backend.helpchain_backend.src.services.public_intake_routing import (
        PUBLIC_INTAKE_SERVICE_CODES,
    )

    admin = _make_admin(
        session, username="public_service_form", email="public_service_form@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name="Service Form", slug="service-form")
    _login_admin(client, admin)
    response = client.get(f"/admin/structures/{st.id}/services/new")

    assert response.status_code == 200
    page = BeautifulSoup(response.data, "html.parser")
    select = page.select_one('select[name="public_intake_service_code"]')
    assert select is not None
    assert not select.has_attr("required")
    assert page.select_one('label[for="public_intake_service_code"]').get_text() == (
        "Service pour les demandes publiques"
    )
    options = {option["value"]: option.get_text(strip=True) for option in select.select("option")}
    assert set(options) == {""} | PUBLIC_INTAKE_SERVICE_CODES
    assert options == {
        "": "Non utilisé pour le routage public",
        "food": "Aide alimentaire",
        "housing": "Logement / hébergement",
        "health": "Santé / accès aux soins",
        "admin": "Aide administrative",
        "orientation": "Orientation vers un service",
    }
    assert select.select_one("option")["value"] == ""
    assert not select.select("option[selected]")

    response = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "Aide alimentaire", "category": "food_assistance",
              "public_intake_service_code": "food"},
    )
    assert response.status_code == 303
    assert StructureService.query.filter_by(structure_id=st.id).one().code == "food"


def test_structure_service_form_preserves_public_selection_on_validation_error(client, session):
    admin = _make_admin(
        session, username="public_form_error", email="public_form_error@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name="Service Form Error", slug="service-form-error")
    _login_admin(client, admin)

    response = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "", "category": "food_assistance", "public_intake_service_code": "food"},
    )

    assert response.status_code == 400
    page = BeautifulSoup(response.data, "html.parser")
    selected = page.select_one('#public_intake_service_code option[selected]')
    assert selected is not None
    assert selected["value"] == "food"


def test_structure_service_create_accepts_valid_category(client, session):
    admin = _make_admin(
        session,
        username="service_creator",
        email="service_creator@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name="Service Owner", slug="service-owner")
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={
            "name": "Accueil social",
            "public_intake_service_code": "",
            "category": "social_support",
            "availability": "available",
            "status": "active",
            "capacity": "5",
            "professionals": "Marie Martin",
            "languages": "français",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    from backend.models import StructureService

    service = StructureService.query.filter_by(structure_id=st.id, name="Accueil social").first()
    assert service is not None
    assert service.category == "social_support"
    assert service.capacity == 5
    assert service.code == "accueil-social"


@pytest.mark.parametrize("code, category", [
    ("food", "food_assistance"),
    ("housing", "housing"),
    ("health", "health"),
    ("admin", "administrative_support"),
    ("orientation", "orientation"),
])
def test_structure_service_create_accepts_explicit_public_intake_code(
    client, session, code, category
):
    from backend.models import StructureService

    admin = _make_admin(
        session, username="public_service_creator",
        email="public_service_creator@test.local", role="superadmin",
    )
    st = _make_structure(session, name="Public Services", slug="public-services")
    _login_admin(client, admin)

    response = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={
            "name": "Service avec nom libre", "category": category,
            "public_intake_service_code": f" {code.upper()} ",
        },
    )

    assert response.status_code == 303
    service = StructureService.query.filter_by(structure_id=st.id).one()
    assert service.code == code
    assert service.is_active


@pytest.mark.parametrize("code", ["unknown", "emergency", "admin_help"])
def test_structure_service_create_rejects_unknown_public_intake_code(client, session, code):
    from backend.models import StructureService

    admin = _make_admin(
        session, username="invalid_public_service",
        email="invalid_public_service@test.local", role="superadmin",
    )
    st = _make_structure(session, name="Invalid Public Code", slug="invalid-public-code")
    _login_admin(client, admin)

    response = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={
            "name": "Service", "category": "social_support",
            "public_intake_service_code": code,
        },
    )

    assert response.status_code == 400
    page = BeautifulSoup(response.data, "html.parser")
    select = page.select_one("#public_intake_service_code")
    assert "is-invalid" in select["class"]
    assert select["aria-describedby"] == "public_intake_service_code_error"
    error = page.select_one("#public_intake_service_code_error.invalid-feedback")
    assert error.get_text(strip=True) == "Code de service public invalide."
    assert StructureService.query.filter_by(structure_id=st.id).count() == 0


@pytest.mark.parametrize("existing_code", ["food", "FOOD"])
def test_structure_service_create_rejects_duplicate_public_code_without_suffix(
    client, session, existing_code
):
    from backend.models import StructureService

    admin = _make_admin(
        session, username="duplicate_public_service",
        email="duplicate_public_service@test.local", role="superadmin",
    )
    st = _make_structure(session, name="Duplicate Public Code", slug="duplicate-public-code")
    session.add(StructureService(
        structure_id=st.id, code=existing_code, name="Existing food service",
        is_active=False,
    ))
    session.commit()
    _login_admin(client, admin)

    response = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={
            "name": "Another food service", "category": "food_assistance",
            "public_intake_service_code": "food",
        },
    )

    assert response.status_code == 400
    page = BeautifulSoup(response.data, "html.parser")
    error = page.select_one("#public_intake_service_code_error.invalid-feedback")
    assert error.get_text(strip=True) == "Ce code de service public existe déjà."
    assert page.select_one('#public_intake_service_code option[selected]')["value"] == "food"
    service = StructureService.query.filter_by(structure_id=st.id).one()
    assert service.code == existing_code
    assert not service.is_active


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capacity", "-1"),
        ("response_sla_hours", "-1"),
        ("capacity", "12.5"),
        ("capacity", "abc"),
        ("capacity", "100001"),
        ("response_sla_hours", "525601"),
    ],
)
def test_structure_service_create_rejects_invalid_capacity_and_sla(client, session, field, value):
    admin = _make_admin(
        session,
        username=f"service_invalid_{field}_{value}".replace("-", "neg").replace(".", "_"),
        email=f"service_invalid_{field}_{value}".replace("-", "neg").replace(".", "_") + "@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name=f"Invalid {field}", slug=f"invalid-{field}-{abs(hash(value))}")
    _login_admin(client, admin)
    data = {"name": "Service borne", "category": "social_support"}
    data[field] = value

    resp = client.post(f"/admin/structures/{st.id}/services/new", data=data, follow_redirects=False)

    assert resp.status_code == 400


def test_structure_service_create_accepts_zero_and_empty_numeric_values(client, session):
    admin = _make_admin(
        session,
        username="service_zero_numeric",
        email="service_zero_numeric@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name="Zero Numeric", slug="zero-numeric")
    _login_admin(client, admin)

    zero_resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={
            "name": "Service zero",
            "category": "social_support",
            "capacity": "0",
            "response_sla_hours": "0",
        },
        follow_redirects=False,
    )
    empty_resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "Service empty", "category": "food_assistance"},
        follow_redirects=False,
    )

    assert zero_resp.status_code == 303
    assert empty_resp.status_code == 303
    from backend.models import StructureService

    zero = StructureService.query.filter_by(structure_id=st.id, name="Service zero").first()
    empty = StructureService.query.filter_by(structure_id=st.id, name="Service empty").first()
    assert zero.capacity == 0
    assert zero.response_sla_hours == 0
    assert empty.capacity is None
    assert empty.response_sla_hours is None


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("referral_required", "yes", True),
        ("referral_required", "no", False),
        ("referral_required", "", None),
        ("emergency_support", "yes", True),
        ("emergency_support", "no", False),
        ("emergency_support", "", None),
    ],
)
def test_structure_service_create_accepts_strict_boolean_values(client, session, field, value, expected):
    admin = _make_admin(
        session,
        username=f"service_bool_{field}_{value or 'empty'}",
        email=f"service_bool_{field}_{value or 'empty'}@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name=f"Bool {field} {value or 'empty'}", slug=f"bool-{field}-{value or 'empty'}")
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "Bool service", "category": "social_support", field: value},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    from backend.models import StructureService

    service = StructureService.query.filter_by(structure_id=st.id, name="Bool service").first()
    assert getattr(service, field) is expected


@pytest.mark.parametrize("field", ["referral_required", "emergency_support"])
def test_structure_service_create_rejects_invalid_boolean_values(client, session, field):
    admin = _make_admin(
        session,
        username=f"service_invalid_bool_{field}",
        email=f"service_invalid_bool_{field}@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name=f"Invalid Bool {field}", slug=f"invalid-bool-{field}")
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "Bool service", "category": "social_support", field: "maybe"},
        follow_redirects=False,
    )

    assert resp.status_code == 400


def test_structure_service_create_rejects_invalid_category(client, session):
    admin = _make_admin(
        session,
        username="service_invalid_category",
        email="service_invalid_category@test.local",
        role="superadmin",
    )
    st = _make_structure(session, name="Invalid Category Owner", slug="invalid-category-owner")
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/new",
        data={"name": "Invented", "category": "invented_category"},
        follow_redirects=False,
    )

    assert resp.status_code == 400


def test_structure_service_detail_is_scoped_to_structure(client, session):
    from backend.models import StructureService

    admin = _make_admin(
        session,
        username="service_scope_admin",
        email="service_scope_admin@test.local",
        role="superadmin",
    )
    own = _make_structure(session, name="Own Service Tenant", slug="own-service-tenant")
    foreign = _make_structure(session, name="Foreign Service Tenant", slug="foreign-service-tenant")
    service = StructureService(
        structure_id=foreign.id,
        code="foreign-service",
        name="Foreign service",
        category="social_support",
    )
    session.add(service)
    session.commit()
    _login_admin(client, admin)

    resp = client.get(
        f"/admin/structures/{own.id}/services/{service.id}",
        follow_redirects=False,
    )

    assert resp.status_code == 404


@pytest.mark.parametrize(
    "path_template",
    [
        "/admin/structures/{foreign_id}/services",
        "/admin/structures/{foreign_id}/services/new",
    ],
)
def test_tenant_admin_cannot_access_foreign_service_pages(client, session, path_template):
    own = _make_structure(session, name="Own Service Scope", slug="own-service-scope")
    foreign = _make_structure(session, name="Foreign Service Scope", slug="foreign-service-scope")
    admin = _make_admin(
        session,
        username="tenant_service_pages_admin",
        email=f"tenant_service_pages_{path_template.count('/') }@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.get(path_template.format(foreign_id=foreign.id), follow_redirects=False)

    assert resp.status_code == 403


def test_tenant_admin_cannot_post_foreign_service_create(client, session):
    from backend.models import StructureService

    own = _make_structure(session, name="Own Service Post", slug="own-service-post")
    foreign = _make_structure(session, name="Foreign Service Post", slug="foreign-service-post")
    admin = _make_admin(
        session,
        username="tenant_service_post_admin",
        email="tenant_service_post_admin@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{foreign.id}/services/new",
        data={"name": "Leaked service", "category": "social_support"},
        follow_redirects=False,
    )

    assert resp.status_code == 403
    assert StructureService.query.filter_by(structure_id=foreign.id, name="Leaked service").first() is None


def test_tenant_admin_cannot_access_foreign_service_detail(client, session):
    from backend.models import StructureService

    own = _make_structure(session, name="Own Detail Scope", slug="own-detail-scope")
    foreign = _make_structure(session, name="Foreign Detail Scope", slug="foreign-detail-scope")
    service = StructureService(
        structure_id=foreign.id,
        code="foreign-service-detail",
        name="Foreign service detail",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="tenant_service_detail_admin",
        email="tenant_service_detail_admin@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.get(
        f"/admin/structures/{foreign.id}/services/{service.id}",
        follow_redirects=False,
    )

    assert resp.status_code == 403


def test_service_workspace_renders_editor(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Render Service", slug="workspace-render-service")
    service = StructureService(
        structure_id=st.id,
        code="workspace-render",
        name="Workspace Render",
        category="social_support",
        status="active",
        availability="available",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_render_admin",
        email="service_workspace_render_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/services/{service.id}", follow_redirects=False)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Espace de travail du service" in body
    assert "Modifier le service" in body
    assert "E-mail du contact" in body
    assert 'name="csrf_token"' in body
    assert "Règles de routage" in body


def test_service_workspace_update_persists_operational_fields(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Update Service", slug="workspace-update-service")
    service = StructureService(
        structure_id=st.id,
        code="workspace-update",
        name="Workspace Update",
        category="social_support",
        status="active",
        availability="available",
        capacity=10,
        is_active=True,
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_update_admin",
        email="service_workspace_update_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={
            "category": "food_assistance",
            "status": "active",
            "availability": "available",
            "priority": "high",
            "risk_level": "critical",
            "description": "Operational desk",
            "notes": "Needs daily monitoring",
            "capacity": "12",
            "available_capacity_override": "7",
            "response_sla_hours": "90",
            "waiting_time_minutes": "45",
            "opening_hours": "24/7",
            "target_population": "Families",
            "eligibility": "Referral required",
            "required_documents": "ID\nProof of address",
            "languages": "fr\nbg",
            "contact_name": "Ops Lead",
            "contact_email": "opslead@test.local",
            "contact_phone": "0102030405",
            "professionals": "Marie Martin\nPaul Dupont",
            "routing_rules": "priority:critical\nterritory:local",
            "referral_required": "yes",
            "emergency_support": "no",
            "territory": "Paris 11e",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(service)
    assert service.category == "food_assistance"
    assert service.priority == "high"
    assert service.risk_level == "critical"
    assert service.capacity == 12
    assert service.available_capacity_override == 7
    assert service.response_sla_hours == 90
    assert service.waiting_time_minutes == 45
    assert service.routing_rules_json is not None
    assert service.contact_name == "Ops Lead"
    assert service.coverage == "Paris 11e"

    intelligence = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)
    payload = intelligence.get_json()
    service_payload = next(item for item in payload["services"] if item["id"] == service.id)
    assert service_payload["available_capacity"] == 7
    assert service_payload["routing_rules"] == ["priority:critical", "territory:local"]
    assert payload["readiness"]["score"] > 0
    assert "Service operating hours" not in payload["readiness"]["missing_information"]
    assert "Configured capacity" not in payload["readiness"]["missing_information"]
    assert payload["services_dashboard"]["assigned_operators"] == 2
    assert payload["services_dashboard"]["services_with_sla"] >= 1
    ai_service = next(
        item
        for item in payload["ai_readiness"]["matching_score_inputs"]["services"]
        if item["service_id"] == service.id
    )
    assert ai_service["routing_rules"] == ["priority:critical", "territory:local"]
    assert ai_service["available_capacity"] == 7


def test_service_workspace_update_rejects_invalid_available_capacity(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Invalid Capacity", slug="workspace-invalid-capacity")
    service = StructureService(
        structure_id=st.id,
        code="workspace-invalid",
        name="Workspace Invalid",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_invalid_admin",
        email="service_workspace_invalid_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={
            "category": "social_support",
            "capacity": "4",
            "available_capacity_override": "5",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(service)
    assert service.available_capacity_override is None


def test_service_workspace_update_unknown_structure_returns_404(client, session):
    admin = _make_admin(
        session,
        username="service_workspace_unknown_structure_admin",
        email="service_workspace_unknown_structure_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        "/admin/structures/999999/services/1/workspace",
        data={"category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code == 404


def test_service_workspace_update_unknown_service_returns_404(client, session):
    st = _make_structure(session, name="Workspace Unknown Service", slug="workspace-unknown-service")
    admin = _make_admin(
        session,
        username="service_workspace_unknown_service_admin",
        email="service_workspace_unknown_service_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/999999/workspace",
        data={"category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code == 404


def test_service_workspace_update_foreign_service_id_returns_404(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Local Service Scope", slug="workspace-local-service-scope")
    foreign = _make_structure(session, name="Workspace Foreign Service Scope", slug="workspace-foreign-service-scope")
    foreign_service = StructureService(
        structure_id=foreign.id,
        code="foreign-scope",
        name="Foreign Scope",
        category="social_support",
    )
    session.add(foreign_service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_foreign_service_admin",
        email="service_workspace_foreign_service_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{foreign_service.id}/workspace",
        data={"category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code == 404


def test_service_workspace_update_requires_authentication(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Save Auth", slug="workspace-save-auth")
    service = StructureService(
        structure_id=st.id,
        code="workspace-save-auth",
        name="Workspace Save Auth",
        category="social_support",
    )
    session.add(service)
    session.commit()

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={"category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert "/admin/login" in (resp.headers.get("Location") or "")


@pytest.mark.parametrize("role", ["admin", "ops", "readonly"])
def test_service_workspace_update_blocks_non_superadmin_roles(client, session, role):
    from backend.models import StructureService

    st = _make_structure(session, name=f"Workspace Role {role}", slug=f"workspace-role-{role}")
    service = StructureService(
        structure_id=st.id,
        code=f"workspace-role-{role}",
        name=f"Workspace Role {role}",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username=f"service_workspace_{role}_admin",
        email=f"service_workspace_{role}_admin@test.local",
        role=role,
        structure_id=st.id,
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={"category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code == 403


def test_service_workspace_update_invalid_values_do_not_partially_persist(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Atomic Save", slug="workspace-atomic-save")
    service = StructureService(
        structure_id=st.id,
        code="workspace-atomic",
        name="Workspace Atomic",
        category="social_support",
        description="Initial description",
        capacity=4,
        available_capacity_override=2,
        priority="medium",
        status="active",
        is_active=True,
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_atomic_admin",
        email="service_workspace_atomic_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={
            "category": "Accompagnement social",
            "status": "bad-status",
            "description": "Should not persist",
            "capacity": "9",
            "available_capacity_override": "3",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(service)
    assert service.status == "active"
    assert service.description == "Initial description"
    assert service.capacity == 4
    assert service.available_capacity_override == 2


def test_service_workspace_update_empty_optional_values_remain_neutral(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Empty Optional", slug="workspace-empty-optional")
    service = StructureService(
        structure_id=st.id,
        code="workspace-empty",
        name="Workspace Empty",
        category="social_support",
        status="active",
        availability="available",
        is_active=True,
        description="Filled",
        notes="Filled",
        capacity=5,
        available_capacity_override=1,
        response_sla_hours=30,
        waiting_time_minutes=15,
        responsible_professionals_json='["Alice"]',
        routing_rules_json='["existing"]',
        contact_name="Lead",
        target_population="Families",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_empty_optional_admin",
        email="service_workspace_empty_optional_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={
            "category": "Accompagnement social",
            "status": "",
            "availability": "",
            "priority": "",
            "risk_level": "",
            "description": "",
            "notes": "",
            "capacity": "",
            "available_capacity_override": "",
            "response_sla_hours": "",
            "waiting_time_minutes": "",
            "opening_hours": "",
            "target_population": "",
            "eligibility": "",
            "required_documents": "",
            "languages": "",
            "contact_name": "",
            "contact_email": "",
            "contact_phone": "",
            "professionals": "",
            "routing_rules": "",
            "referral_required": "",
            "emergency_support": "",
            "territory": "",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(service)
    assert service.description is None
    assert service.notes is None
    assert service.capacity is None
    assert service.available_capacity_override is None
    assert service.response_sla_hours is None
    assert service.waiting_time_minutes is None
    assert service.contact_name is None
    assert service.routing_rules_json is None

    detail = client.get(f"/admin/structures/{st.id}/services/{service.id}", follow_redirects=False)
    body = detail.get_data(as_text=True)
    assert detail.status_code == 200
    assert "Description non renseign" in body
    assert "Aucune règle de routage" in body


def test_service_workspace_update_duplicate_submission_is_safe(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace Duplicate Save", slug="workspace-duplicate-save")
    service = StructureService(
        structure_id=st.id,
        code="workspace-duplicate",
        name="Workspace Duplicate",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_duplicate_admin",
        email="service_workspace_duplicate_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    payload = {
        "category": "Accompagnement social",
        "status": "active",
        "availability": "available",
        "capacity": "8",
        "available_capacity_override": "6",
        "routing_rules": "priority:high",
    }

    first = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data=payload,
        follow_redirects=False,
    )
    second = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data=payload,
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert second.status_code == 303
    session.refresh(service)
    assert StructureService.query.filter_by(structure_id=st.id, code="workspace-duplicate").count() == 1
    assert service.available_capacity_override == 6
    assert service.routing_rules_json == '["priority:high"]'


def test_service_workspace_post_accepts_valid_csrf_when_enabled(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace CSRF", slug="workspace-csrf")
    service = StructureService(
        structure_id=st.id,
        code="workspace-csrf",
        name="Workspace CSRF",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_csrf_admin",
        email="service_workspace_csrf_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    client.application.config["WTF_CSRF_ENABLED"] = True

    page = client.get(f"/admin/structures/{st.id}/services/{service.id}", follow_redirects=False)
    token = _extract_csrf(page.get_data(as_text=True))
    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={"csrf_token": token, "category": "Accompagnement social"},
        follow_redirects=False,
    )

    assert resp.status_code == 303


def test_service_workspace_update_escapes_stored_html_on_reload(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Workspace XSS", slug="workspace-xss")
    service = StructureService(
        structure_id=st.id,
        code="workspace-xss",
        name="Workspace XSS",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="service_workspace_xss_admin",
        email="service_workspace_xss_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    script = '<script>alert("xss")</script>'

    resp = client.post(
        f"/admin/structures/{st.id}/services/{service.id}/workspace",
        data={
            "category": "Accompagnement social",
            "description": script,
            "notes": script,
            "eligibility": script,
            "routing_rules": script,
            "contact_name": script,
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    detail = client.get(f"/admin/structures/{st.id}/services/{service.id}", follow_redirects=False)
    body = detail.get_data(as_text=True)
    assert "<script>alert(" not in body
    assert "&lt;script&gt;alert" in body


def test_tenant_admin_cannot_post_foreign_service_workspace(client, session):
    from backend.models import StructureService

    own = _make_structure(session, name="Own Service Workspace", slug="own-service-workspace")
    foreign = _make_structure(session, name="Foreign Service Workspace", slug="foreign-service-workspace")
    service = StructureService(
        structure_id=foreign.id,
        code="foreign-workspace",
        name="Foreign Workspace",
        category="social_support",
    )
    session.add(service)
    session.commit()
    admin = _make_admin(
        session,
        username="tenant_service_workspace_admin",
        email="tenant_service_workspace_admin@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{foreign.id}/services/{service.id}/workspace",
        data={"category": "social_support"},
        follow_redirects=False,
    )

    assert resp.status_code == 403


def test_service_catalog_uses_french_business_labels(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Business Labels", slug="business-labels")
    admin = _make_admin(
        session,
        username="business_labels_admin",
        email="business_labels_admin@test.local",
        role="superadmin",
    )
    session.add(
        StructureService(
            structure_id=st.id,
            code="social",
            name="Accueil social",
            category="social_support",
            availability="available",
            status="active",
            is_active=True,
        )
    )
    session.commit()
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["services"][0]["category"] == "Accompagnement social"
    assert payload["services"][0]["availability"] == "Disponible"
    assert payload["ai_readiness"]["matching_score_inputs"]["services"][0]["category"] == "Accompagnement social"


def test_ai_routing_includes_only_explicitly_routable_services(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Routing Eligibility", slug="routing-eligibility")
    admin = _make_admin(
        session,
        username="routing_eligibility_admin",
        email="routing_eligibility_admin@test.local",
        role="superadmin",
    )
    services = [
        StructureService(
            structure_id=st.id,
            code="active-available",
            name="Actif disponible",
            category="social_support",
            status="active",
            availability="available",
            is_active=True,
        ),
        StructureService(
            structure_id=st.id,
            code="inactive",
            name="Inactif",
            category="social_support",
            status="active",
            availability="available",
            is_active=False,
        ),
        StructureService(
            structure_id=st.id,
            code="unavailable",
            name="Indisponible",
            category="social_support",
            status="active",
            availability="unavailable",
            is_active=True,
        ),
        StructureService(
            structure_id=st.id,
            code="missing-availability",
            name="Disponibilité manquante",
            category="social_support",
            status="active",
            availability="",
            is_active=True,
        ),
    ]
    session.add_all(services)
    session.commit()
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert resp.status_code == 200
    routing = resp.get_json()["ai_readiness"]["matching_score_inputs"]
    assert [item["name"] for item in routing["routable_services"]] == ["Actif disponible"]
    non_routable = {item["name"]: item["reason"] for item in routing["non_routable_services"]}
    assert non_routable["Inactif"] == "Service inactif"
    assert non_routable["Indisponible"] == "Disponibilité non confirmée"
    assert non_routable["Disponibilité manquante"] == "Disponibilité non confirmée"


def test_french_localization_hides_targeted_english_business_labels(client, session):
    from backend.models import StructureService

    st = _make_structure(session, name="Clinique Locale", slug="clinique-locale")
    st.organization_type = "clinic"
    session.add(
        StructureService(
            structure_id=st.id,
            code="social",
            name="Accueil social",
            category="social_support",
            status="active",
            availability="available",
            is_active=True,
        )
    )
    session.commit()
    admin = _make_admin(
        session,
        username="french_labels_admin",
        email="french_labels_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    detail = client.get(f"/admin/structures/{st.id}", follow_redirects=False).get_data(as_text=True)
    services = client.get(f"/admin/structures/{st.id}/services", follow_redirects=False).get_data(as_text=True)
    service_id = StructureService.query.filter_by(structure_id=st.id, code="social").first().id
    service_detail = client.get(
        f"/admin/structures/{st.id}/services/{service_id}",
        follow_redirects=False,
    ).get_data(as_text=True)
    combined = "\n".join([detail, services, service_detail])

    assert "Clinique" in combined
    for forbidden in [
        "Clinic",
        "Not enough operational data",
        "requests.city inferred from active data",
        "Health Explainability",
        "Service Detail",
        "Matching score inputs",
        "social_support",
    ]:
        assert forbidden not in combined


def test_operational_intelligence_uses_french_confidence_and_source(client, session):
    st = _make_structure(session, name="French Confidence", slug="french-confidence")
    admin = _make_admin(
        session,
        username="french_confidence_admin",
        email="french_confidence_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["coverage"]["confidence"] == "faible"
    assert payload["coverage"]["source"] == "Données déduites des villes présentes dans les demandes actives"
    assert payload["profile"]["organization_type"]["label"] != "Clinic"


def test_assign_admin_success(client, session):
    st = _make_structure(session, name="Assign", slug="assign")
    global_admin = _make_admin(
        session, username="assign_global", email="assign_global@test.local", role="superadmin"
    )
    target_admin = _make_admin(
        session, username="assign_target", email="assign_target@test.local", role="admin"
    )
    _login_admin(client, global_admin)
    resp = client.post(
        f"/admin/structures/{st.id}/assign-admin",
        data={"admin_id": str(target_admin.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    session.refresh(target_admin)
    assert target_admin.structure_id == st.id


@pytest.mark.parametrize("admin_id", ["", "not-an-int", "999999"])
def test_assign_admin_invalid_id(client, session, admin_id):
    st = _make_structure(session, name="AssignBad", slug="assign-bad")
    global_admin = _make_admin(
        session, username="assign_bad_global", email="assign_bad_global@test.local", role="superadmin"
    )
    target_admin = _make_admin(
        session, username="assign_bad_target", email="assign_bad_target@test.local", role="admin"
    )
    _login_admin(client, global_admin)
    resp = client.post(
        f"/admin/structures/{st.id}/assign-admin",
        data={"admin_id": admin_id},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    session.refresh(target_admin)
    assert target_admin.structure_id is None


def test_tenant_scoping_global_admin_unfiltered(client, session):
    st1 = _make_structure(session, name="Tenant 1", slug="tenant-1")
    st2 = _make_structure(session, name="Tenant 2", slug="tenant-2")
    u1 = _make_user(session, username="u1", email="u1@test.local")
    u2 = _make_user(session, username="u2", email="u2@test.local")
    _make_request(session, title="Req 1", user_id=u1.id, structure_id=st1.id)
    _make_request(session, title="Req 2", user_id=u2.id, structure_id=st2.id)

    global_admin = _make_admin(
        session, username="global_ops", email="global_ops@test.local", role="superadmin"
    )
    _login_admin(client, global_admin)
    resp = client.get("/admin/api/ops-kpis", follow_redirects=False)
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert int(payload.get("new_requests") or 0) == 2


def test_tenant_scoping_structure_bound_admin_filtered(client, session):
    st1 = _make_structure(session, name="Tenant 1b", slug="tenant-1b")
    st2 = _make_structure(session, name="Tenant 2b", slug="tenant-2b")
    u1 = _make_user(session, username="u1b", email="u1b@test.local")
    u2 = _make_user(session, username="u2b", email="u2b@test.local")
    _make_request(session, title="Req 1b", user_id=u1.id, structure_id=st1.id)
    _make_request(session, title="Req 2b", user_id=u2.id, structure_id=st2.id)

    scoped_admin = _make_admin(
        session,
        username="scoped_admin",
        email="scoped_admin@test.local",
        role="admin",
        structure_id=st1.id,
    )
    _login_admin(client, scoped_admin)
    resp = client.get("/admin/api/ops-kpis", follow_redirects=False)
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert int(payload.get("new_requests") or 0) == 1


def test_operational_intelligence_includes_readiness_for_empty_workspace(client, session):
    st = _make_structure(session, name="Readiness Empty", slug="readiness-empty")
    admin = _make_admin(
        session,
        username="readiness_empty_admin",
        email="readiness_empty_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["readiness"]["score"] == 0
    assert "Operational contacts" in payload["readiness"]["missing_information"]
    assert payload["executive_kpis"][0]["label"] == "Readiness"
    assert payload["executive_kpis"][0]["display"] == "0%"


def test_readiness_score_is_bounded_and_deterministic(client, session):
    from backend.models import StructureContact, StructureCoverageArea, StructureService

    st = _make_structure(session, name="Readiness Full", slug="readiness-full")
    st.status = "active"
    st.email = "ops@readiness.test"
    st.phone = "0101010101"
    st.opening_hours = "24/7"
    session.add(
        StructureContact(
            structure_id=st.id,
            contact_type="operational",
            name="Ops Lead",
            email="lead@readiness.test",
            preferred_communication="phone",
            is_active=True,
        )
    )
    session.add(
        StructureService(
            structure_id=st.id,
            code="ready-service",
            name="Ready Service",
            category="social_support",
            status="active",
            availability="available",
            opening_hours="24/7",
            capacity=12,
            is_active=True,
        )
    )
    session.add(
        StructureCoverageArea(
            structure_id=st.id,
            area_type="city",
            name="Paris",
            is_active=True,
        )
    )
    session.commit()
    admin = _make_admin(
        session,
        username="readiness_full_admin",
        email="readiness_full_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    first = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)
    second = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.get_json()
    second_payload = second.get_json()
    assert 0 <= first_payload["readiness"]["score"] <= 100
    assert first_payload["readiness"] == second_payload["readiness"]
    assert any("géométrie" in item for item in first_payload["readiness"]["recommendations"])


def test_structure_workspace_update_persists_enterprise_fields(client, session):
    st = _make_structure(session, name="Workspace Update", slug="workspace-update")
    admin = _make_admin(
        session,
        username="workspace_update_admin",
        email="workspace_update_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/workspace",
        data={
            "status": "active",
            "organization_type": "ccas",
            "risk_level": "high",
            "description": "Coordination locale",
            "email": "ops@workspace.test",
            "phone": "+33123456789",
            "opening_hours": "24/7",
            "departments": "75\n92",
            "capabilities": "social_support\ncase_coordination",
            "languages": "fr\nbg",
            "priority_domains": "housing",
            "accepted_case_types": "family_support",
            "required_documents": "ID",
            "supported_populations": "families",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(st)
    assert st.status == "active"
    assert st.organization_type == "ccas"
    assert st.email == "ops@workspace.test"
    assert st.departments_json is not None
    assert st.capabilities_json is not None


def test_structure_contact_create_persists_preferred_communication(client, session):
    from backend.models import StructureContact

    st = _make_structure(session, name="Contact Owner", slug="contact-owner")
    admin = _make_admin(
        session,
        username="contact_create_admin",
        email="contact_create_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/contacts/new",
        data={
            "contact_type": "operational",
            "name": "Marie Ops",
            "role": "Coordinator",
            "email": "marie@example.test",
            "phone": "0102030405",
            "availability": "Weekdays",
            "preferred_communication": "phone",
            "escalation_order": "1",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    contact = StructureContact.query.filter_by(structure_id=st.id, name="Marie Ops").first()
    assert contact is not None
    assert contact.contact_type == "operational"
    assert contact.preferred_communication == "phone"


def test_structure_contact_create_rejects_empty_contact_payload(client, session):
    from backend.models import StructureContact

    st = _make_structure(session, name="Contact Empty", slug="contact-empty")
    admin = _make_admin(
        session,
        username="contact_empty_admin",
        email="contact_empty_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/contacts/new",
        data={"contact_type": "operational"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert StructureContact.query.filter_by(structure_id=st.id).count() == 0


def test_structure_contact_create_deduplicates_exact_contact(client, session):
    from backend.models import StructureContact

    st = _make_structure(session, name="Contact Duplicate", slug="contact-duplicate")
    admin = _make_admin(
        session,
        username="contact_duplicate_admin",
        email="contact_duplicate_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    data = {
        "contact_type": "operational",
        "name": "Marie Ops",
        "role": "Coordinator",
        "email": "marie@example.test",
        "phone": "0102030405",
        "preferred_communication": "phone",
    }

    first = client.post(f"/admin/structures/{st.id}/contacts/new", data=data, follow_redirects=False)
    second = client.post(f"/admin/structures/{st.id}/contacts/new", data=data, follow_redirects=False)

    assert first.status_code == 303
    assert second.status_code == 303
    assert StructureContact.query.filter_by(structure_id=st.id, name="Marie Ops").count() == 1


def test_structure_coverage_create_supports_phase5_fields(client, session):
    from backend.models import StructureCoverageArea

    st = _make_structure(session, name="Coverage Owner", slug="coverage-owner")
    admin = _make_admin(
        session,
        username="coverage_create_admin",
        email="coverage_create_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/coverage/new",
        data={
            "area_type": "commune",
            "name": "Nanterre",
            "postal_code": "92000",
            "department": "Hauts-de-Seine",
            "region": "Ile-de-France",
            "administrative_code": "92050",
            "coverage_radius_km": "12",
            "population_served": "96000",
            "geometry_kind": "external_reference",
            "geometry_data_json": '{"source":"insee"}',
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    area = StructureCoverageArea.query.filter_by(structure_id=st.id, name="Nanterre").first()
    assert area is not None
    assert area.area_type == "commune"
    assert area.region == "Ile-de-France"
    assert area.administrative_code == "92050"
    assert area.geometry_kind == "external_reference"

    intelligence = client.get(f"/admin/structures/{st.id}/operational-intelligence", follow_redirects=False)
    payload = intelligence.get_json()
    assert "Nanterre" in payload["coverage"]["covered_communes"]
    assert "Ile-de-France" in payload["coverage"]["regions"]


def test_structure_coverage_create_rejects_invalid_geometry_json(client, session):
    from backend.models import StructureCoverageArea

    st = _make_structure(session, name="Coverage Invalid JSON", slug="coverage-invalid-json")
    admin = _make_admin(
        session,
        username="coverage_invalid_json_admin",
        email="coverage_invalid_json_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(
        f"/admin/structures/{st.id}/coverage/new",
        data={"area_type": "city", "name": "Paris", "geometry_data_json": "{not-json}"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert StructureCoverageArea.query.filter_by(structure_id=st.id).count() == 0


def test_structure_coverage_create_deduplicates_same_area(client, session):
    from backend.models import StructureCoverageArea

    st = _make_structure(session, name="Coverage Duplicate", slug="coverage-duplicate")
    admin = _make_admin(
        session,
        username="coverage_duplicate_admin",
        email="coverage_duplicate_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)
    data = {"area_type": "city", "name": "Paris"}

    first = client.post(f"/admin/structures/{st.id}/coverage/new", data=data, follow_redirects=False)
    second = client.post(f"/admin/structures/{st.id}/coverage/new", data=data, follow_redirects=False)

    assert first.status_code == 303
    assert second.status_code == 303
    assert StructureCoverageArea.query.filter_by(structure_id=st.id, name="Paris").count() == 1


@pytest.mark.parametrize(
    "path",
    [
        "/admin/structures/999999/workspace",
        "/admin/structures/999999/contacts/new",
        "/admin/structures/999999/coverage/new",
    ],
)
def test_workspace_mutations_return_404_for_unknown_structure(client, session, path):
    admin = _make_admin(
        session,
        username="unknown_structure_admin",
        email="unknown_structure_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.post(path, data={}, follow_redirects=False)

    assert resp.status_code == 404


@pytest.mark.parametrize(
    "path,data",
    [
        ("/admin/structures/{foreign_id}/workspace", {"status": "active"}),
        ("/admin/structures/{foreign_id}/contacts/new", {"contact_type": "primary"}),
        ("/admin/structures/{foreign_id}/coverage/new", {"area_type": "city", "name": "Paris"}),
    ],
)
def test_tenant_admin_cannot_post_foreign_workspace_mutations(client, session, path, data):
    own = _make_structure(session, name="Own Workspace Scope", slug="own-workspace-scope")
    foreign = _make_structure(session, name="Foreign Workspace Scope", slug="foreign-workspace-scope")
    admin = _make_admin(
        session,
        username="tenant_workspace_admin",
        email="tenant_workspace_admin@test.local",
        role="superadmin",
        structure_id=own.id,
    )
    _login_admin(client, admin)

    resp = client.post(path.format(foreign_id=foreign.id), data=data, follow_redirects=False)

    assert resp.status_code == 403


@pytest.mark.parametrize(
    "path,data",
    [
        ("/admin/structures/{structure_id}/workspace", {"status": "active"}),
        ("/admin/structures/{structure_id}/contacts/new", {"contact_type": "primary", "name": "Ops"}),
        ("/admin/structures/{structure_id}/coverage/new", {"area_type": "city", "name": "Paris"}),
    ],
)
def test_workspace_mutations_require_authentication(client, session, path, data):
    st = _make_structure(session, name="Auth Workspace", slug="auth-workspace")

    resp = client.post(path.format(structure_id=st.id), data=data, follow_redirects=False)

    assert resp.status_code in (302, 303)
    assert "/admin/login" in (resp.headers.get("Location") or "")


def test_structure_dashboard_renders_empty_workspace_safely(client, session):
    st = _make_structure(session, name="Render Empty", slug="render-empty")
    admin = _make_admin(
        session,
        username="render_empty_admin",
        email="render_empty_admin@test.local",
        role="superadmin",
    )
    _login_admin(client, admin)

    resp = client.get(f"/admin/structures/{st.id}", follow_redirects=False)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Readiness" in body
    assert "Ajouter un contact" in body
    assert "Ajouter une zone" in body
    assert "col-12 col-md-6" in body


@pytest.mark.parametrize("role", ["ops", "readonly"])
def test_ops_readonly_cannot_access_structure_routes(client, session, role):
    admin = _make_admin(
        session,
        username=f"{role}_admin",
        email=f"{role}_admin@test.local",
        role=role,
    )
    _login_admin(client, admin)
    resp = client.get("/admin/structures", follow_redirects=False)
    assert resp.status_code == 403
