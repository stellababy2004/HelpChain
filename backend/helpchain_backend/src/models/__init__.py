import json
from datetime import UTC, datetime
from enum import Enum

import pyotp
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


try:
    # Prefer the canonical package-qualified extensions module so we reuse the
    # same SQLAlchemy() instance used by the application.
    from backend.extensions import db  # type: ignore
except Exception:  # pragma: no cover - fallback for legacy layouts
    # Fall back to the canonical package-qualified import to preserve
    # compatibility with environments that rely on the old import layout.
    from backend.extensions import db


class AdminRole(Enum):
    """Роли в административната система"""

    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


"""
Shim module for `helpchain_backend.src.models` to avoid duplicate ORM
declarations. Export canonical model classes from the top-level `models`.

This keeps existing imports in the codebase working while ensuring SQLAlchemy
only registers each mapped class once.
"""

try:
    from backend.models import (
        AdminUser,
        Feedback,
        Request,
        RequestLog,
        User,
        Volunteer,
    )
except Exception:  # pragma: no cover - fallback for legacy layouts
    from backend.models import (
        AdminUser,
        Feedback,
        Request,
        RequestLog,
        User,
        Volunteer,
    )

__all__ = [
    "Request",
    "RequestLog",
    "Volunteer",
    "Feedback",
    "AdminUser",
    "User",
]
