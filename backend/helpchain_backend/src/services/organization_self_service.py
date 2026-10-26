from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from backend.extensions import db
from backend.models import AdminUser, Structure, utc_now
from backend.helpchain_backend.src.models import PendingOrganizationSignup
from backend.helpchain_backend.src.services.enterprise_structure_intelligence import ORGANIZATION_TYPES

PURPOSE = "organization_signup_verification"
TTL_MINUTES = 30
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def validate_signup(*, organization_name: str, email: str, password: str, organization_type: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    email = normalize_email(email)
    organization_type = (organization_type or "").strip().lower()
    if not (organization_name or "").strip():
        errors["organization_name"] = "Le nom de l'organisation est requis."
    if not EMAIL_RE.match(email):
        errors["email"] = "Merci d'indiquer une adresse e-mail valide."
    if organization_type not in ORGANIZATION_TYPES:
        errors["organization_type"] = "Le type d'organisation sélectionné est invalide."
    if len(password or "") < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        errors["password"] = "Le mot de passe doit contenir 8 caractères, une majuscule, une minuscule et un chiffre."
    return errors


def duplicate_reason(organization_name: str, email: str) -> str | None:
    email = normalize_email(email)
    if db.session.query(AdminUser.id).filter(func.lower(AdminUser.email) == email).first():
        return "email_exists"
    if db.session.query(PendingOrganizationSignup.id).filter(
        func.lower(PendingOrganizationSignup.email) == email,
        PendingOrganizationSignup.consumed_at.is_(None),
        PendingOrganizationSignup.expires_at > utc_now(),
    ).first():
        return "email_pending"
    if db.session.query(Structure.id).filter(func.lower(Structure.name) == organization_name.strip().lower()).first():
        return "organization_exists"
    return None


def create_pending_signup(*, organization_name: str, contact_name: str, email: str, password: str, organization_type: str):
    raw_token = secrets.token_urlsafe(32)
    admin = AdminUser(password_hash="")
    admin.set_password(password)
    row = PendingOrganizationSignup(
        email=normalize_email(email),
        contact_name=contact_name.strip(),
        organization_name=organization_name.strip(),
        organization_type=organization_type.strip().lower(),
        password_hash=admin.password_hash,
        verification_token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(minutes=TTL_MINUTES),
    )
    db.session.add(row)
    db.session.flush()
    return row, raw_token


def verify_and_provision(raw_token: str) -> tuple[Structure, AdminUser]:
    token_hash = hashlib.sha256((raw_token or "").encode()).hexdigest()
    now = utc_now()
    row = PendingOrganizationSignup.query.filter_by(verification_token_hash=token_hash).first()
    expires_at = _as_utc(row.expires_at) if row is not None else None
    if row is None or row.consumed_at is not None or expires_at is None or expires_at <= _as_utc(now):
        raise ValueError("invalid_verification")
    try:
        claimed = PendingOrganizationSignup.query.filter(
            PendingOrganizationSignup.id == row.id,
            PendingOrganizationSignup.consumed_at.is_(None),
            PendingOrganizationSignup.expires_at > now,
        ).update({"consumed_at": now, "verified_at": now}, synchronize_session=False)
        if not claimed:
            raise ValueError("invalid_verification")
        if duplicate_reason(row.organization_name, row.email):
            raise ValueError("duplicate_signup")
        base = re.sub(r"[^a-z0-9]+", "-", row.organization_name.lower()).strip("-") or "org"
        slug, index = base, 2
        while db.session.query(Structure.id).filter(func.lower(Structure.slug) == slug.lower()).first():
            slug, index = f"{base}-{index}", index + 1
        username_base = re.sub(r"[^a-z0-9]+", "_", (row.contact_name or row.email.split("@", 1)[0]).lower()).strip("_") or "admin"
        username, index = username_base, 2
        while db.session.query(AdminUser.id).filter(func.lower(AdminUser.username) == username.lower()).first():
            username, index = f"{username_base}_{index}", index + 1
        structure = Structure(name=row.organization_name, slug=slug, organization_type=row.organization_type, status="active")
        db.session.add(structure)
        db.session.flush()
        admin = AdminUser(
            username=username,
            email=row.email,
            password_hash=row.password_hash,
            role="admin",
            is_active=True,
            structure_id=structure.id,
            must_change_password=True,
            onboarding_step="welcome",
        )
        db.session.add(admin)
        db.session.flush()
        return structure, admin
    except Exception:
        db.session.rollback()
        raise
