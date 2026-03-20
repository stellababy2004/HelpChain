from __future__ import annotations

import logging

from sqlalchemy import func

from backend.extensions import db
import re

from backend.helpchain_backend.src.models import AdminUser, Structure

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


def create_structure_with_admin(name: str, admin_email: str, password: str) -> tuple[int, int]:
    if not name or not admin_email or not password:
        raise ValueError("name, admin_email, and password are required")

    normalized_name = name.strip()
    normalized_email = admin_email.strip().lower()

    existing_structure = (
        db.session.query(Structure)
        .filter(func.lower(Structure.name) == normalized_name.lower())
        .first()
    )
    if existing_structure:
        raise ValueError("structure_name_exists")

    existing_admin = (
        db.session.query(AdminUser)
        .filter(func.lower(AdminUser.email) == normalized_email)
        .first()
    )
    if existing_admin:
        raise ValueError("admin_email_exists")

    with db.session.begin():
        slug = _unique_slug(_slugify(normalized_name))
        structure = Structure(name=normalized_name, slug=slug)
        if hasattr(structure, "status"):
            structure.status = "active"
        db.session.add(structure)
        db.session.flush()

        admin = AdminUser(
            username=f"admin_{normalized_name.lower().replace(' ', '_')}",
            email=normalized_email,
            role="admin",
            is_active=True,
            structure_id=structure.id,
            password_hash="",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        log.info("Structure created: %s", structure.name)

        return int(structure.id), int(admin.id)
