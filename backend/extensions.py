"""
Compatibility wrapper.

Do NOT create extension instances here.
Re-export the canonical ones from backend.helpchain_backend.src.extensions.
"""

from backend.helpchain_backend.src.extensions import babel, db, mail, migrate

__all__ = ["db", "mail", "babel", "migrate"]
