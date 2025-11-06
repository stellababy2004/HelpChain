"""Package shim for the project root.

This file ensures imports like `from backend.models import ...` resolve to the
single canonical `models` module object, preventing the same ORM classes
from being defined multiple times under different module names which causes
SQLAlchemy registration conflicts.
"""
import sys

try:
    # If the top-level `models` module is already loaded, alias it as
    # `backend.models` so all imports point to the same module object.
    if 'models' in sys.modules:
        sys.modules.setdefault('backend.models', sys.modules['models'])
    else:
        # Otherwise import it now and register both names
        import models as _models
        sys.modules.setdefault('backend.models', _models)
except Exception:
    # Best-effort only; tests will still attempt to import backend.models and
    # Python will raise normally if it cannot be resolved.
    pass

__all__ = ['models']
# празен файл
