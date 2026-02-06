"""
Compatibility wrapper.

Re-export the canonical extension instances from backend.helpchain_backend.src.extensions.
Do NOT instantiate new objects here to avoid multiple SQLAlchemy MetaData registries.
"""

from backend.helpchain_backend.src.extensions import (
    db,
    mail,
    babel,
    migrate,
    limiter,
    csrf,
)

__all__ = ["db", "mail", "babel", "migrate", "limiter", "csrf"]
