"""Organization account recovery using the existing magic-link token store."""

import hashlib
import secrets
from datetime import timedelta

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer

from backend.models import AdminUser, db, utc_now
from ..models.magic_link_token import MagicLinkToken

PURPOSE = "admin_access_reset"
TTL_MINUTES = 30


def _serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=PURPOSE)


def _fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()


def invalidate_access_resets(email):
    MagicLinkToken.query.filter_by(
        purpose=PURPOSE, email=email, used_at=None, invalidated_at=None
    ).update({"invalidated_at": utc_now(), "invalidated_reason": "account_changed"},
             synchronize_session=False)


def create_self_access_reset(user):
    """Create a password-reset token requested by the account owner."""
    if (
        user is None
        or not user.is_active
        or not user.email
        or user.role not in {"admin", "ops", "readonly", "superadmin"}
    ):
        raise ValueError("reset_not_allowed")

    invalidate_access_resets(user.email)

    raw = _serializer().dumps({
        "user": user.id,
        "structure": user.structure_id,
        "issuer": None,
        "self_service": True,
        "password": _fingerprint(user),
        "nonce": secrets.token_urlsafe(32),
    })

    row = MagicLinkToken(
        purpose=PURPOSE,
        email=user.email,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(minutes=TTL_MINUTES),
    )
    db.session.add(row)
    db.session.flush()
    return row, raw


def create_access_reset(user, actor, *, allow_platform_admin=False):
    if not actor.is_authenticated or not user.is_active:
        raise ValueError("reset_not_allowed")

    is_org_admin = (
        actor.role == "admin"
        and actor.structure_id is not None
        and user.structure_id == actor.structure_id
        and user.role in {"admin", "ops", "readonly"}
    )

    is_platform_admin = (
        allow_platform_admin
        and actor.role == "superadmin"
        and user.role in {"admin", "ops", "readonly", "superadmin"}
    )

    if not (is_org_admin or is_platform_admin):
        raise ValueError("reset_not_allowed")

    issuer_id = getattr(actor, "admin_id", None)
    if issuer_id is None:
        issuer_id = getattr(actor, "id", None)
    if issuer_id is None:
        raise ValueError("reset_not_allowed")

    invalidate_access_resets(user.email)
    raw = _serializer().dumps({
        "user": user.id, "structure": user.structure_id,
        "issuer": issuer_id, "password": _fingerprint(user),
        "nonce": secrets.token_urlsafe(32),
    })
    row = MagicLinkToken(
        purpose=PURPOSE, email=user.email,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(minutes=TTL_MINUTES),
    )
    db.session.add(row)
    db.session.flush()
    return row, raw


def consume_access_reset(raw, password):
    try:
        data = _serializer().loads(raw)
    except BadSignature:
        raise ValueError("invalid_reset") from None
    if not isinstance(data, dict):
        raise ValueError("invalid_reset")
    user = AdminUser.query.filter_by(
        id=data.get("user"), structure_id=data.get("structure"), is_active=True
    ).first()
    is_self_service = bool(data.get("self_service"))

    if is_self_service:
        issuer_valid = data.get("issuer") is None
        role_valid = user is not None and user.role in {
            "admin", "ops", "readonly", "superadmin"
        }
    else:
        issuer = AdminUser.query.filter_by(
            id=data.get("issuer"),
            is_active=True,
        ).first()
        issuer_valid = (
            issuer is not None
            and (
                (
                    issuer.role == "admin"
                    and issuer.structure_id == data.get("structure")
                )
                or issuer.role == "superadmin"
            )
        )
        role_valid = user is not None and user.role in {
            "admin", "ops", "readonly", "superadmin"
        }

    if (
        user is None
        or not issuer_valid
        or not role_valid
        or _fingerprint(user) != data.get("password")
    ):
        raise ValueError("invalid_reset")
    # Validate with the canonical policy without changing the persistent object.
    candidate = AdminUser()
    candidate.set_password(password)
    now = utc_now()
    claimed = MagicLinkToken.query.filter(
        MagicLinkToken.token_hash == hashlib.sha256(raw.encode()).hexdigest(),
        MagicLinkToken.purpose == PURPOSE,
        MagicLinkToken.email == user.email,
        MagicLinkToken.used_at.is_(None),
        MagicLinkToken.invalidated_at.is_(None),
        MagicLinkToken.expires_at > now,
    ).update({"used_at": now}, synchronize_session=False)
    if not claimed:
        raise ValueError("invalid_reset")
    changed = AdminUser.query.filter_by(
        id=user.id, structure_id=data["structure"], is_active=True,
        password_hash=user.password_hash, role=user.role,
    ).update({"password_hash": candidate.password_hash, "must_change_password": False},
             synchronize_session=False)
    if not changed:
        raise ValueError("invalid_reset")
    invalidate_access_resets(user.email)
    db.session.flush()
    return user
