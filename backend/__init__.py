"""Package shim for the project root.

This file ensures imports like `from backend.models import ...` resolve to the
single canonical `models` module object, preventing the same ORM classes
from being defined multiple times under different module names which causes
SQLAlchemy registration conflicts.
"""

import importlib
import sys

try:
    # Prefer the package-qualified canonical module `backend.models` as the
    # single source of truth. When available, ensure the unqualified
    # import name `models` points to the same module object so older code
    # that does `from models import X` continues to work without creating
    # duplicate module objects.
    try:
        _bm = importlib.import_module("backend.models")
        # Make `models` refer to the canonical backend.models module if
        # it's not already set to the same object.
        if sys.modules.get("models") is not _bm:
            sys.modules.setdefault("models", _bm)
    except Exception:
        # If `backend.models` can't be imported yet, but a top-level
        # `models` module exists, register it under `backend.models` so
        # package-qualified imports still resolve to the same object.
        if "models" in sys.modules:
            sys.modules.setdefault("backend.models", sys.modules["models"])
        else:
            # Attempt to import the short-name `models` and ensure both
            # names exist; this is best-effort to help older layouts.
            try:
                _models = importlib.import_module("models")
                sys.modules.setdefault("backend.models", _models)
            except Exception:
                # Give up quietly; importing modules later will raise normally.
                pass
except Exception:
    # Best-effort only; if anything fails here we don't want to break normal
    # module import semantics during application startup.
    pass

__all__ = ["models"]
# празен файл
