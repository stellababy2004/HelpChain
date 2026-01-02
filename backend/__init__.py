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


__all__ = []
