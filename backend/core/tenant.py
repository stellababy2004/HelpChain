from __future__ import annotations

import os

from flask import g, has_app_context
from sqlalchemy.exc import OperationalError, ProgrammingError

from backend.extensions import db
from backend.models import Structure

_DEFAULT_STRUCTURE_ID: int | None = None
TENANT_DEFAULT_SLUG = os.getenv("HC_DEFAULT_STRUCTURE_SLUG", "default")


def _is_test_env() -> bool:
    return (
        os.getenv("HC_ENV") == "test"
        or os.getenv("HELPCHAIN_TESTING") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def _load_default_structure_id() -> int:
    global _DEFAULT_STRUCTURE_ID
    if _DEFAULT_STRUCTURE_ID is None:
        try:
            default = (
                db.session.query(Structure)
                .filter(Structure.slug == TENANT_DEFAULT_SLUG)
                .first()
            )
        except (OperationalError, ProgrammingError):
            if _is_test_env():
                # Legacy tests may call app.test_client() before DB bootstrap.
                _DEFAULT_STRUCTURE_ID = 1
                return _DEFAULT_STRUCTURE_ID
            raise
        if not default:
            raise RuntimeError("Default structure not found in DB.")
        _DEFAULT_STRUCTURE_ID = int(default.id)
    return _DEFAULT_STRUCTURE_ID


def current_structure_id() -> int:
    if not has_app_context():
        return _load_default_structure_id()

    if hasattr(g, "structure_id"):
        return int(g.structure_id)

    if hasattr(g, "user") and getattr(g.user, "structure_id", None):
        g.structure_id = int(g.user.structure_id)
        return int(g.structure_id)

    g.structure_id = _load_default_structure_id()
    return int(g.structure_id)
