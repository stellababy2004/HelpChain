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
    # Fallback: dynamically import the backend.permissions module and
    # copy public symbols into this module's globals to preserve the
    # compatibility shim without using a star-relative import.
    try:
        import importlib

        _mod = importlib.import_module("backend.permissions")
        for _name in dir(_mod):
            if not _name.startswith("_"):
                try:
                    globals()[_name] = getattr(_mod, _name)
                except Exception:
                    pass
    except Exception:
        # As a last resort, re-raise so test imports fail loudly.
        raise

__all__ = [
    name
    for name in dir()
    if not name.startswith("_") and name not in ("__name__", "__doc__")
]
