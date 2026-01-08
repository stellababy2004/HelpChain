from backend.models import *  # noqa


# --- Canonical model imports (legacy compatibility shim) ---
# Your repository currently has other parts importing `Request`, `User`, etc.
# BUT they are not defined inside this `src/models/` package yet.
# We try to import them from their canonical location(s) WITHOUT hard-failing.
#
# Replace/extend these import paths once you confirm where the real models live.
_CANDIDATE_MODEL_MODULES = (
    "backend.models",                 # common pattern: backend/models.py
    "backend.models.models",          # sometimes: backend/models/models.py
    "backend.models.base",            # sometimes: backend/models/base.py
)

_IMPORTED = {}
for _mod in _CANDIDATE_MODEL_MODULES:
    try:
        module = __import__(_mod, fromlist=["*"])
    except Exception:
        continue

    # Pick only the names you want to re-export if they exist in that module.
    for _name in (
        "AdminUser",
        "Request",
        "RequestLog",
        "User",
        "Volunteer",
        "PushSubscription",
        "Feedback",
    ):
        if hasattr(module, _name):
            _IMPORTED[_name] = getattr(module, _name)

# Expose imported names in this module namespace (if any were found)
globals().update(_IMPORTED)


# --- Public API ---
# Export db + whatever models we actually managed to import.
__all__ = ["db", *sorted(_IMPORTED.keys())]

