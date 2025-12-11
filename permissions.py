"""
Compatibility shim so tests importing the top-level `permissions`
module resolve to `backend.permissions` implementation used by the app.

This prevents test-time imports like `from permissions import ...`
from accidentally loading a missing top-level module and ensures the
seeding and helper functions are the same implementation the app uses.
"""

try:
    # Prefer the backend package implementation; import module and re-export
    import importlib

    _bp = importlib.import_module("backend.permissions")
    for _name in dir(_bp):
        if _name.startswith("_"):
            continue
        globals()[_name] = getattr(_bp, _name)
except Exception:
    # Fallback: try to import a local module if present and re-export
    try:
        import importlib

        _bp = importlib.import_module("backend.permissions")
        for _name in dir(_bp):
            if _name.startswith("_"):
                continue
            globals()[_name] = getattr(_bp, _name)
    except Exception:
        # As a last resort, re-raise the import error so tests fail loudly
        raise

__all__ = [
    name
    for name in globals().keys()
    if not name.startswith("_") and name not in ("__name__", "__doc__")
]
