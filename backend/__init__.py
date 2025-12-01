"""Package shim for the project root.

This module intentionally avoids importing `backend.models` at package
import time. Importing `backend.models` eagerly caused metadata/engine
initialization to run before the Flask app's `db.init_app()` in test
fixtures, producing mismatched SQLAlchemy registries and missing table
visibility during tests. To remain compatible with older code that imports
`models` directly, we only alias module names if one of them is already
loaded by the import system.

Usage:
- If `backend.models` is imported before this module, we ensure `models`
  (top-level short-name) points to the same module object.
- If a top-level `models` module exists, we register it under
  `backend.models` so package-qualified imports resolve consistently.

This lazy approach prevents import-order races while remaining
backwards-compatible.
"""

import sys

# If `backend.models` already loaded, make sure `models` points to it.
if "backend.models" in sys.modules:
    bm = sys.modules["backend.models"]
    if sys.modules.get("models") is not bm:
        sys.modules.setdefault("models", bm)
else:
    # If a top-level `models` module exists (older layouts), register it as
    # `backend.models` so imports like `from backend.models import X` succeed.
    if "models" in sys.modules:
        sys.modules.setdefault("backend.models", sys.modules["models"])

__all__ = ["models"]
