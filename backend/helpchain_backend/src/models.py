"""
Robust shim to ensure `helpchain_backend.src.models` always references the
canonical model module used by the application. Some environments import
models under different module names which can cause SQLAlchemy to register
the same mapped classes multiple times. To avoid that, we import the
canonical `backend.models` (or fallback to `models`) and alias it in
sys.modules under common names. We then re-export the public attributes so
`from helpchain_backend.src.models import X` works as before.

Do NOT define new model classes in this file; update `backend.models`.
"""

import importlib
import sys


def _load_canonical_models():
    # Prefer the package-qualified canonical module; fall back to legacy
    # top-level module name if necessary.
    try:
        mod = importlib.import_module("backend.models")
    except Exception:
        mod = importlib.import_module("models")
    return mod


_canonical = _load_canonical_models()

# Alias common import names to the single canonical module object so that
# any subsequent imports using alternate paths resolve to the same module
# object (prevents duplicate mapper registration).
for alias in ("models", "backend.models", "helpchain_backend.src.models"):
    try:
        sys.modules[alias] = _canonical
    except Exception:
        pass

# Re-export public names from the canonical module into this module namespace
for _name in dir(_canonical):
    if _name.startswith("_"):
        continue
    try:
        globals()[_name] = getattr(_canonical, _name)
    except Exception:
        pass

try:
    __all__ = [n for n in dir(_canonical) if not n.startswith("_")]
except Exception:
    __all__ = []
