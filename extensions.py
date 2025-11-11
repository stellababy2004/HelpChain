"""Top-level shim that re-exports the canonical extension objects.

This module re-exports `db`, `babel`, `mail`, and `cache` from
`backend.extensions` so legacy `import extensions` code paths resolve
to the same canonical objects used by the package. Do NOT instantiate
SQLAlchemy() here.
"""

try:
    from backend.extensions import babel, cache, db, mail  # type: ignore
except Exception:
    # If the canonical package module isn't available (e.g. during
    # early import in some scripts), expose safe placeholders instead
    # to avoid hard import failures.
    db = None
    babel = None
    mail = None
    cache = None

__all__ = ["db", "babel", "mail", "cache"]
