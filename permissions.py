"""
Compatibility shim so tests importing the top-level `permissions`
module resolve to `backend.permissions` implementation used by the app.

This prevents test-time imports like `from permissions import ...`
from accidentally loading a missing top-level module and ensures the
seeding and helper functions are the same implementation the app uses.
"""
try:
    # Prefer the backend package implementation
    from backend.permissions import *  # noqa: F401,F403
except Exception:
    # Fallback: try to import a local module if present
    try:
        from .backend.permissions import *  # type: ignore
    except Exception:
        # As a last resort, raise the original ImportError so tests fail
        raise

__all__ = [
    name
    for name in dir()
    if not name.startswith("_") and name not in ("__name__", "__doc__")
]
