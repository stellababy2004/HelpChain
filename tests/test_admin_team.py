from __future__ import annotations

from datetime import timedelta

from backend.models import (
    AdminUser,
    AdminUserInvitation,
    Structure,
    db,
    utc_now,
)


def _admin(username: str, structure_id: int, role: str = "admin") -> AdminUser:
    admin = AdminUser(
        username=username,
        email=f"{username}@helpchain.local",
        password_hash="x",
        role=role,
        is_active=True,
        structure_id=structure_id,
        mfa_enabled=True,
        totp_secret="test",
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _login(client, app, admin: AdminUser) -> None:
    with client.session_transaction() as session:
        session.clear()
        session["_user_id"] = str(admin.id)
        session["user_id"] = admin.id
        session["role"] = admin.role
        session["is_authenticated"] = True
        session["is_admin"] = True
        session["admin_logged_in"] = True
        session["admin_id"] = admin.id
        session["admin_user_id"] = admin.id
        session[app.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
        session["mfa_ok_until"] = (
            utc_now() + timedelta(minutes=30)
        ).isoformat()
        session["admin_mfa_last_verified"] = 4102444800
        session["admin_mfa_user_id"] = admin.id


def test_admin_team_is_tenant_scoped(client, app):
    structure_a = Structure(
        name="Team Tenant A",
        slug="team-tenant-a",
        status="active",
    )
    structure_b = Structure(
        name="Team Tenant B",
        slug="team-tenant-b",
        status="active",
    )
    db.session.add_all([structure_a, structure_b])
    db.session.flush()

    admin_a = _admin("team_admin_a", structure_a.id)
    member_a = _admin("visible_member_a", structure_a.id, role="ops")
    member_b = _admin("hidden_member_b", structure_b.id, role="ops")

    now = utc_now()

    invitation_a = AdminUserInvitation(
        structure_id=structure_a.id,
        invited_by_admin_id=admin_a.id,
        email="visible-invite-a@example.test",
        role="readonly",
        token_hash="a" * 64,
        created_at=now,
        expires_at=now + timedelta(hours=48),
    )
    invitation_b = AdminUserInvitation(
        structure_id=structure_b.id,
        invited_by_admin_id=member_b.id,
        email="hidden-invite-b@example.test",
        role="readonly",
        token_hash="b" * 64,
        created_at=now,
        expires_at=now + timedelta(hours=48),
    )

    db.session.add_all([invitation_a, invitation_b])
    db.session.commit()

    _login(client, app, admin_a)

    response = client.get("/admin/team")

    assert response.status_code == 200

    body = response.get_data(as_text=True)

    assert admin_a.email in body
    assert member_a.email in body
    assert invitation_a.email in body

    assert member_b.email not in body
    assert invitation_b.email not in body


def test_admin_team_invite_cannot_override_structure(client, app):
    structure_a = Structure(
        name="Invite Tenant A",
        slug="invite-tenant-a",
        status="active",
    )
    structure_b = Structure(
        name="Invite Tenant B",
        slug="invite-tenant-b",
        status="active",
    )
    db.session.add_all([structure_a, structure_b])
    db.session.flush()

    admin_a = _admin("invite_admin_a", structure_a.id)
    db.session.commit()

    _login(client, app, admin_a)

    response = client.post(
        "/admin/team/invite",
        data={
            "email": "new-member@example.test",
            "role": "ops",
            "structure_id": str(structure_b.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    invitation = AdminUserInvitation.query.filter_by(
        email="new-member@example.test"
    ).one()

    assert invitation.structure_id == structure_a.id
    assert invitation.structure_id != structure_b.id
    assert invitation.invited_by_admin_id == admin_a.id
    assert invitation.role == "ops"
    assert len(invitation.token_hash) == 64


def test_admin_team_invitation_end_to_end(client, app, monkeypatch):
    structure = Structure(
        name="Invitation E2E Tenant",
        slug="invitation-e2e-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("invitation_e2e_admin", structure.id)
    db.session.commit()

    captured = {}

    def fake_send(recipient, subject, template, context, **kwargs):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["template"] = template
        captured["context"] = dict(context)
        captured["kwargs"] = dict(kwargs)
        return True

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        fake_send,
    )

    _login(client, app, admin)

    invited_email = "invited-user@example.test"

    response = client.post(
        "/admin/team/invite",
        data={
            "email": invited_email,
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    invitation = AdminUserInvitation.query.filter_by(
        email=invited_email
    ).one()

    assert invitation.structure_id == structure.id
    assert invitation.invited_by_admin_id == admin.id
    assert invitation.role == "ops"
    assert invitation.accepted_at is None
    assert invitation.revoked_at is None
    assert len(invitation.token_hash) == 64

    assert captured["recipient"] == invited_email
    assert captured["template"] == "emails/admin_team_invitation.html"
    assert captured["kwargs"]["purpose"] == "admin_team_invitation"
    assert captured["kwargs"]["structure_id"] == structure.id

    invitation_url = captured["context"]["invitation_url"]
    assert "/team/invitation/" in invitation_url

    raw_token = invitation_url.rsplit("/", 1)[-1]

    assert raw_token
    assert raw_token not in invitation.token_hash

    accept_response = client.post(
        f"/team/invitation/{raw_token}",
        data={
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
        },
        follow_redirects=False,
    )

    assert accept_response.status_code == 303

    db.session.expire_all()

    created_user = AdminUser.query.filter_by(
        email=invited_email
    ).one()

    assert created_user.structure_id == structure.id
    assert created_user.role == "ops"
    assert created_user.is_active is True
    assert created_user.check_password("SecurePass123") is True

    invitation = AdminUserInvitation.query.filter_by(
        email=invited_email
    ).one()

    assert invitation.accepted_at is not None

    second_response = client.post(
        f"/team/invitation/{raw_token}",
        data={
            "password": "AnotherPass123",
            "confirm_password": "AnotherPass123",
        },
        follow_redirects=False,
    )

    assert second_response.status_code == 400

    assert (
        AdminUser.query.filter_by(email=invited_email).count()
        == 1
    )

def test_admin_team_invite_rejects_superadmin(client, app):
    structure = Structure(
        name="Role Security Tenant",
        slug="role-security-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("role_security_admin", structure.id)
    db.session.commit()

    _login(client, app, admin)

    response = client.post(
        "/admin/team/invite",
        data={
            "email": "forbidden-superadmin@example.test",
            "role": "superadmin",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        AdminUserInvitation.query.filter_by(
            email="forbidden-superadmin@example.test"
        ).count()
        == 0
    )

    assert (
        AdminUser.query.filter_by(
            email="forbidden-superadmin@example.test"
        ).count()
        == 0
    )

def test_admin_team_invite_rejects_existing_user_email(client, app):
    structure = Structure(
        name="Duplicate Email Tenant",
        slug="duplicate-email-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("duplicate_email_admin", structure.id)
    existing_user = _admin(
        "existing_team_member",
        structure.id,
        role="ops",
    )
    db.session.commit()

    _login(client, app, admin)

    response = client.post(
        "/admin/team/invite",
        data={
            "email": existing_user.email,
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        AdminUserInvitation.query.filter_by(
            email=existing_user.email
        ).count()
        == 0
    )

    assert (
        AdminUser.query.filter_by(
            email=existing_user.email
        ).count()
        == 1
    )

def test_admin_team_invite_rejects_duplicate_pending_invitation(client, app):
    structure = Structure(
        name="Pending Duplicate Tenant",
        slug="pending-duplicate-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("pending_duplicate_admin", structure.id)
    db.session.commit()

    _login(client, app, admin)

    email = "pending-duplicate@example.test"

    first_response = client.post(
        "/admin/team/invite",
        data={
            "email": email,
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert first_response.status_code == 303

    second_response = client.post(
        "/admin/team/invite",
        data={
            "email": email,
            "role": "admin",
        },
        follow_redirects=False,
    )

    assert second_response.status_code == 303

    invitations = AdminUserInvitation.query.filter_by(
        email=email
    ).all()

    assert len(invitations) == 1
    assert invitations[0].structure_id == structure.id
    assert invitations[0].role == "ops"
    assert invitations[0].accepted_at is None
    assert invitations[0].revoked_at is None

def test_admin_team_invite_rolls_back_when_email_fails(
    client,
    app,
    monkeypatch,
):
    structure = Structure(
        name="Email Failure Tenant",
        slug="email-failure-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("email_failure_admin", structure.id)
    db.session.commit()

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: False,
    )

    _login(client, app, admin)

    email = "email-failure@example.test"

    response = client.post(
        "/admin/team/invite",
        data={
            "email": email,
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        AdminUserInvitation.query.filter_by(
            email=email
        ).count()
        == 0
    )

    assert (
        AdminUser.query.filter_by(
            email=email
        ).count()
        == 0
    )

import pytest


@pytest.mark.parametrize("role", ["ops", "readonly"])
def test_non_admin_cannot_manage_team(client, app, role):
    structure = Structure(
        name=f"Restricted Team {role}",
        slug=f"restricted-team-{role}",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    user = _admin(
        f"restricted_{role}",
        structure.id,
        role=role,
    )
    db.session.commit()

    _login(client, app, user)

    get_response = client.get(
        "/admin/team",
        follow_redirects=False,
    )

    assert get_response.status_code == 403

    post_response = client.post(
        "/admin/team/invite",
        data={
            "email": f"blocked-{role}@example.test",
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert post_response.status_code == 403

    assert (
        AdminUserInvitation.query.filter_by(
            email=f"blocked-{role}@example.test"
        ).count()
        == 0
    )

@pytest.mark.parametrize("structure_attached", [False, True])
def test_superadmin_cannot_manage_organization_team(
    client,
    app,
    structure_attached,
):
    structure = Structure(
        name=f"Superadmin Team {structure_attached}",
        slug=f"superadmin-team-{str(structure_attached).lower()}",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    superadmin = _admin(
        f"team_superadmin_{str(structure_attached).lower()}",
        structure.id,
        role="superadmin",
    )

    if not structure_attached:
        superadmin.structure_id = None

    db.session.commit()

    _login(client, app, superadmin)

    response = client.get(
        "/admin/team",
        follow_redirects=False,
    )

    assert response.status_code == 403

    invite_response = client.post(
        "/admin/team/invite",
        data={
            "email": (
                f"blocked-superadmin-"
                f"{str(structure_attached).lower()}@example.test"
            ),
            "role": "ops",
        },
        follow_redirects=False,
    )

    assert invite_response.status_code == 403

    assert (
        AdminUserInvitation.query.filter_by(
            email=(
                f"blocked-superadmin-"
                f"{str(structure_attached).lower()}@example.test"
            )
        ).count()
        == 0
    )

def test_expired_admin_team_invitation_cannot_be_accepted(client, app):
    structure = Structure(
        name="Expired Invitation Tenant",
        slug="expired-invitation-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("expired_invitation_admin", structure.id)

    raw_token = "expired-invitation-test-token"

    from backend.helpchain_backend.src.services.admin_team_invitations import (
        hash_invitation_token,
    )

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="expired-invite@example.test",
        role="ops",
        token_hash=hash_invitation_token(raw_token),
        created_at=utc_now() - timedelta(hours=49),
        expires_at=utc_now() - timedelta(hours=1),
    )

    db.session.add(invitation)
    db.session.commit()

    response = client.get(
        f"/team/invitation/{raw_token}",
        follow_redirects=False,
    )

    assert response.status_code == 400

    assert (
        AdminUser.query.filter_by(
            email="expired-invite@example.test"
        ).count()
        == 0
    )

    invitation = db.session.get(
        AdminUserInvitation,
        invitation.id,
    )

    assert invitation.accepted_at is None
    assert invitation.revoked_at is None

def test_revoked_admin_team_invitation_cannot_be_accepted(client, app):
    structure = Structure(
        name="Revoked Invitation Tenant",
        slug="revoked-invitation-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("revoked_invitation_admin", structure.id)

    raw_token = "revoked-invitation-test-token"

    from backend.helpchain_backend.src.services.admin_team_invitations import (
        hash_invitation_token,
    )

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="revoked-invite@example.test",
        role="ops",
        token_hash=hash_invitation_token(raw_token),
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(hours=48),
        revoked_at=utc_now(),
    )

    db.session.add(invitation)
    db.session.commit()

    response = client.get(
        f"/team/invitation/{raw_token}",
        follow_redirects=False,
    )

    assert response.status_code == 400

    assert (
        AdminUser.query.filter_by(
            email="revoked-invite@example.test"
        ).count()
        == 0
    )

    invitation = db.session.get(
        AdminUserInvitation,
        invitation.id,
    )

    assert invitation.accepted_at is None
    assert invitation.revoked_at is not None

def test_admin_team_invitation_smtp_failure_redacts_email_diagnostic(client, monkeypatch, caplog):
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

    raw_token = "diagnostic-secret-admin-invitation-token"
    invitation_url = f"https://helpchain.test/team/invitation/{raw_token}"

    monkeypatch.setattr(
        mail_service,
        "render_template",
        lambda template, **context: invitation_url,
    )

    def fail_smtp(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", fail_smtp)

    email_log = mock_open()
    monkeypatch.setattr(mail_service, "open", email_log, raising=False)

    with client.application.app_context():
        assert mail_service.send_notification_email(
            "invitee@test.local",
            "Invitation à rejoindre HelpChain",
            "emails/admin_team_invitation.html",
            {
                "invitation_url": invitation_url,
                "structure_name": "Test Organization",
                "role": "ops",
                "ttl_hours": 48,
            },
            purpose="admin_team_invitation",
            structure_id=1,
        ) is False

    email_log.assert_called_once_with(
        "sent_emails.txt",
        "a",
        encoding="utf-8",
    )

    diagnostic = "".join(
        call.args[0] for call in email_log().write.call_args_list
    )

    assert "[Sensitive email body redacted]" in diagnostic
    assert raw_token not in diagnostic + caplog.text
    assert invitation_url not in diagnostic + caplog.text


def test_admin_team_can_revoke_own_tenant_invitation(client, app):
    structure = Structure(
        name="Revoke Tenant",
        slug="revoke-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("revoke_admin", structure.id)

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="revoke-me@example.test",
        role="ops",
        token_hash="c" * 64,
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(hours=48),
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_id = invitation.id
    _login(client, app, admin)

    response = client.post(
        f"/admin/team/invitations/{invitation_id}/revoke",
        follow_redirects=False,
    )

    assert response.status_code == 303

    revoked = db.session.get(AdminUserInvitation, invitation_id)
    assert revoked is not None
    assert revoked.revoked_at is not None
    assert revoked.accepted_at is None


def test_admin_team_cannot_revoke_other_tenant_invitation(client, app):
    structure_a = Structure(
        name="Revoke Tenant A",
        slug="revoke-tenant-a",
        status="active",
    )
    structure_b = Structure(
        name="Revoke Tenant B",
        slug="revoke-tenant-b",
        status="active",
    )
    db.session.add_all([structure_a, structure_b])
    db.session.flush()

    admin_a = _admin("revoke_admin_a", structure_a.id)
    admin_b = _admin("revoke_admin_b", structure_b.id)

    invitation = AdminUserInvitation(
        structure_id=structure_b.id,
        invited_by_admin_id=admin_b.id,
        email="protected-invite@example.test",
        role="readonly",
        token_hash="d" * 64,
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(hours=48),
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_id = invitation.id
    _login(client, app, admin_a)

    response = client.post(
        f"/admin/team/invitations/{invitation_id}/revoke",
        follow_redirects=False,
    )

    assert response.status_code == 404

    protected = db.session.get(AdminUserInvitation, invitation_id)
    assert protected is not None
    assert protected.revoked_at is None
    assert protected.accepted_at is None


def test_admin_team_invitation_refresh_rotates_token(client, app):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        InvitationInvalid,
        get_admin_team_invitation,
        hash_invitation_token,
        refresh_admin_team_invitation,
    )

    with app.app_context():
        structure = Structure(
            name="Refresh Token Tenant",
            slug="refresh-token-tenant",
            status="active",
        )
        db.session.add(structure)
        db.session.flush()

        admin = _admin("refresh_token_admin", structure.id)

        old_token = "old-secret-invitation-token"
        invitation = AdminUserInvitation(
            structure_id=structure.id,
            invited_by_admin_id=admin.id,
            email="refresh-token@example.test",
            role="ops",
            token_hash=hash_invitation_token(old_token),
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(hours=48),
        )
        db.session.add(invitation)
        db.session.commit()

        invitation_id = invitation.id

        new_token = refresh_admin_team_invitation(invitation)
        db.session.commit()

        assert new_token != old_token
        assert invitation.token_hash == hash_invitation_token(new_token)
        assert invitation.token_hash != hash_invitation_token(old_token)

        try:
            get_admin_team_invitation(old_token)
        except InvitationInvalid:
            pass
        else:
            raise AssertionError(
                "Old invitation token must be invalid after refresh"
            )

        refreshed = get_admin_team_invitation(new_token)
        assert refreshed.id == invitation_id



def test_admin_team_resend_email_failure_preserves_old_token(
    client,
    app,
    monkeypatch,
):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        get_admin_team_invitation,
        hash_invitation_token,
    )

    structure = Structure(
        name="Resend Failure Tenant",
        slug="resend-failure-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("resend_failure_admin", structure.id)

    old_token = "still-valid-old-token"
    old_expires_at = utc_now() + timedelta(hours=24)

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="resend-failure@example.test",
        role="ops",
        token_hash=hash_invitation_token(old_token),
        created_at=utc_now(),
        expires_at=old_expires_at,
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_id = invitation.id
    old_hash = invitation.token_hash

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: False,
    )

    _login(client, app, admin)

    response = client.post(
        f"/admin/team/invitations/{invitation_id}/resend",
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.session.expire_all()

    preserved = db.session.get(AdminUserInvitation, invitation_id)

    assert preserved is not None
    assert preserved.token_hash == old_hash
    assert preserved.expires_at.replace(tzinfo=None) == old_expires_at.replace(tzinfo=None)
    assert preserved.accepted_at is None
    assert preserved.revoked_at is None

    valid_old_invitation = get_admin_team_invitation(old_token)
    assert valid_old_invitation.id == invitation_id


def test_admin_team_resend_success_rotates_token(
    client,
    app,
    monkeypatch,
):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        InvitationInvalid,
        get_admin_team_invitation,
        hash_invitation_token,
    )

    structure = Structure(
        name="Resend Success Tenant",
        slug="resend-success-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("resend_success_admin", structure.id)

    old_token = "old-resend-success-token"

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="resend-success@example.test",
        role="readonly",
        token_hash=hash_invitation_token(old_token),
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(hours=24),
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_id = invitation.id
    old_hash = invitation.token_hash
    captured = {}

    def fake_send(recipient, subject, template, context, **kwargs):
        captured["recipient"] = recipient
        captured["context"] = dict(context)
        captured["kwargs"] = dict(kwargs)
        return True

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        fake_send,
    )

    _login(client, app, admin)

    response = client.post(
        f"/admin/team/invitations/{invitation_id}/resend",
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.session.expire_all()

    refreshed = db.session.get(AdminUserInvitation, invitation_id)

    assert refreshed is not None
    assert refreshed.structure_id == structure.id
    assert refreshed.token_hash != old_hash
    assert refreshed.accepted_at is None
    assert refreshed.revoked_at is None

    invitation_url = captured["context"]["invitation_url"]
    new_token = invitation_url.rsplit("/", 1)[-1]

    assert new_token
    assert new_token != old_token
    assert refreshed.token_hash == hash_invitation_token(new_token)

    try:
        get_admin_team_invitation(old_token)
    except InvitationInvalid:
        pass
    else:
        raise AssertionError(
            "Old token must be invalid after successful resend"
        )

    current = get_admin_team_invitation(new_token)
    assert current.id == invitation_id

    assert captured["recipient"] == invitation.email
    assert captured["kwargs"]["purpose"] == "admin_team_invitation"
    assert captured["kwargs"]["structure_id"] == structure.id


def test_admin_team_cannot_resend_other_tenant_invitation(
    client,
    app,
    monkeypatch,
):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        hash_invitation_token,
    )

    structure_a = Structure(
        name="Resend Tenant A",
        slug="resend-tenant-a",
        status="active",
    )
    structure_b = Structure(
        name="Resend Tenant B",
        slug="resend-tenant-b",
        status="active",
    )
    db.session.add_all([structure_a, structure_b])
    db.session.flush()

    admin_a = _admin("resend_admin_a", structure_a.id)
    admin_b = _admin("resend_admin_b", structure_b.id)

    old_token = "protected-cross-tenant-token"

    invitation = AdminUserInvitation(
        structure_id=structure_b.id,
        invited_by_admin_id=admin_b.id,
        email="protected-resend@example.test",
        role="ops",
        token_hash=hash_invitation_token(old_token),
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(hours=48),
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_id = invitation.id
    old_hash = invitation.token_hash

    mail_calls = []

    def fake_send(*args, **kwargs):
        mail_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        fake_send,
    )

    _login(client, app, admin_a)

    response = client.post(
        f"/admin/team/invitations/{invitation_id}/resend",
        follow_redirects=False,
    )

    assert response.status_code == 404

    db.session.expire_all()

    protected = db.session.get(AdminUserInvitation, invitation_id)

    assert protected is not None
    assert protected.structure_id == structure_b.id
    assert protected.token_hash == old_hash
    assert protected.accepted_at is None
    assert protected.revoked_at is None
    assert mail_calls == []

def test_admin_team_expired_invitation_remains_visible(client, app):
    from backend.helpchain_backend.src.services.admin_team_invitations import (
        hash_invitation_token,
    )

    structure = Structure(
        name="Expired Visible Tenant",
        slug="expired-visible-tenant",
        status="active",
    )
    db.session.add(structure)
    db.session.flush()

    admin = _admin("expired_visible_admin", structure.id)

    invitation = AdminUserInvitation(
        structure_id=structure.id,
        invited_by_admin_id=admin.id,
        email="expired-visible@example.test",
        role="ops",
        token_hash=hash_invitation_token("expired-visible-token"),
        created_at=utc_now() - timedelta(hours=72),
        expires_at=utc_now() - timedelta(hours=24),
    )

    db.session.add(invitation)
    db.session.commit()

    _login(client, app, admin)

    response = client.get("/admin/team")

    assert response.status_code == 200

    body = response.get_data(as_text=True)

    assert "expired-visible@example.test" in body
    assert "Renvoyer" in body
