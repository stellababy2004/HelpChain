from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, AdminUserInvitation


INVITATION_TTL_HOURS = 48
INVITABLE_ROLES = {"admin", "ops", "readonly"}


class InvitationEmailAlreadyUsed(ValueError):
    pass


class InvitationAlreadyPending(ValueError):
    pass


class InvitationRoleNotAllowed(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_admin_team_invitation(
    *,
    structure_id: int,
    invited_by_admin_id: int,
    email: str,
    role: str,
    ttl_hours: int = INVITATION_TTL_HOURS,
) -> tuple[AdminUserInvitation, str]:
    normalized_email = _normalize_email(email)
    normalized_role = (role or "").strip().lower()

    if not normalized_email or "@" not in normalized_email:
        raise ValueError("invalid_email")

    if normalized_role not in INVITABLE_ROLES:
        raise InvitationRoleNotAllowed("role_not_allowed")

    existing_user = (
        db.session.query(AdminUser.id)
        .filter(func.lower(AdminUser.email) == normalized_email)
        .first()
    )
    if existing_user is not None:
        raise InvitationEmailAlreadyUsed("email_already_used")

    now = _now()

    existing_invitation = (
        AdminUserInvitation.query.filter(
            AdminUserInvitation.structure_id == structure_id,
            func.lower(AdminUserInvitation.email) == normalized_email,
            AdminUserInvitation.accepted_at.is_(None),
            AdminUserInvitation.revoked_at.is_(None),
            AdminUserInvitation.expires_at > now,
        )
        .first()
    )
    if existing_invitation is not None:
        raise InvitationAlreadyPending("invitation_already_pending")

    raw_token = secrets.token_urlsafe(32)

    invitation = AdminUserInvitation(
        structure_id=structure_id,
        invited_by_admin_id=invited_by_admin_id,
        email=normalized_email,
        role=normalized_role,
        token_hash=hash_invitation_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )

    db.session.add(invitation)
    db.session.flush()

    return invitation, raw_token


class InvitationInvalid(ValueError):
    pass


class InvitationExpired(ValueError):
    pass


class InvitationAlreadyUsed(ValueError):
    pass


class InvitationRevoked(ValueError):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_admin_team_invitation(raw_token: str) -> AdminUserInvitation:
    token = (raw_token or "").strip()
    if not token:
        raise InvitationInvalid("invalid_invitation")

    invitation = AdminUserInvitation.query.filter_by(
        token_hash=hash_invitation_token(token)
    ).first()

    if invitation is None:
        raise InvitationInvalid("invalid_invitation")

    if invitation.revoked_at is not None:
        raise InvitationRevoked("invitation_revoked")

    if invitation.accepted_at is not None:
        raise InvitationAlreadyUsed("invitation_already_used")

    if _as_utc(invitation.expires_at) <= _now():
        raise InvitationExpired("invitation_expired")

    return invitation


def accept_admin_team_invitation(
    *,
    raw_token: str,
    password: str,
) -> AdminUser:
    invitation = get_admin_team_invitation(raw_token)

    existing_user = (
        db.session.query(AdminUser.id)
        .filter(func.lower(AdminUser.email) == invitation.email.lower())
        .first()
    )
    if existing_user is not None:
        raise InvitationEmailAlreadyUsed("email_already_used")

    # Import the existing canonical username generator instead of duplicating it.
    from backend.helpchain_backend.src.services.organization_onboarding import (
        _unique_admin_username,
    )

    user = AdminUser(
        username=_unique_admin_username(None, invitation.email),
        email=invitation.email,
        role=invitation.role,
        is_active=True,
        structure_id=invitation.structure_id,
        password_hash="",
        must_change_password=False,
    )

    # Reuse AdminUser's existing password policy + Werkzeug hashing.
    user.set_password(password)

    # Claim only a still-valid invitation. This write competes atomically with
    # revocation, including when the invitation was read before cancellation.
    now = _now()
    claimed = AdminUserInvitation.query.filter(
        AdminUserInvitation.id == invitation.id,
        AdminUserInvitation.token_hash == hash_invitation_token(raw_token.strip()),
        AdminUserInvitation.accepted_at.is_(None),
        AdminUserInvitation.revoked_at.is_(None),
        AdminUserInvitation.expires_at > now,
    ).update({AdminUserInvitation.accepted_at: now}, synchronize_session=False)
    if not claimed:
        raise InvitationInvalid("invalid_invitation")

    db.session.add(user)
    db.session.flush()

    db.session.refresh(invitation)

    return user


def refresh_admin_team_invitation(
    invitation: AdminUserInvitation,
    *,
    ttl_hours: int = INVITATION_TTL_HOURS,
) -> str:
    """Rotate an invitation token and extend its validity for resend."""

    if invitation.revoked_at is not None:
        raise InvitationRevoked("invitation_revoked")

    if invitation.accepted_at is not None:
        raise InvitationAlreadyUsed("invitation_already_used")

    raw_token = secrets.token_urlsafe(32)
    now = _now()

    invitation.token_hash = hash_invitation_token(raw_token)
    invitation.created_at = now
    invitation.expires_at = now + timedelta(hours=ttl_hours)

    db.session.flush()

    return raw_token
