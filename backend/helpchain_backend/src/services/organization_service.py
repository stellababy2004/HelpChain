from __future__ import annotations

import logging
import re

from sqlalchemy import func

from backend.extensions import db
from backend.models import User
from backend.helpchain_backend.src.models import Structure

log = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return base or "org"


def _unique_slug(base: str) -> str:
    slug = base
    idx = 2
    while (
        db.session.query(Structure.id)
        .filter(func.lower(Structure.slug) == slug.lower())
        .first()
        is not None
    ):
        slug = f"{base}-{idx}"
        idx += 1
    return slug


def register_organization(data: dict) -> tuple[int, int]:
    name = (data.get("organization_name") or "").strip()
    admin_email = (data.get("admin_email") or "").strip().lower()
    admin_name = (data.get("admin_name") or "").strip()
    password = data.get("password") or ""

    if not name:
        raise ValueError("invalid_name")
    if not admin_email:
        raise ValueError("invalid_email")
    if not admin_name:
        raise ValueError("invalid_admin_name")
    if len(password) < 10:
        raise ValueError("password_too_short")

    existing_structure = (
        db.session.query(Structure)
        .filter(func.lower(Structure.name) == name.lower())
        .first()
    )
    if existing_structure:
        raise ValueError("organization_exists")

    existing_user = (
        db.session.query(User)
        .filter(func.lower(User.email) == admin_email)
        .first()
    )
    if existing_user:
        raise ValueError("email_exists")

    slug = _unique_slug(_slugify(name))
    structure = Structure(name=name, slug=slug, status="pending")
    db.session.add(structure)
    db.session.flush()

    admin = User(
        username=admin_name,
        email=admin_email,
        role="admin",
        structure_id=structure.id,
        password_hash="",
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.flush()

    log.info("Structure created: %s", structure.name)
    db.session.commit()
    return int(structure.id), int(admin.id)
