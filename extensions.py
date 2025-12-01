# Compatibility shim: expose the same objects as `backend.extensions` under the
# top-level name `extensions` so legacy imports that do `import extensions`
# or `from extensions import db` behave consistently during tests.
try:
    from backend.extensions import db, mail, babel, cache  # type: ignore
except Exception:
    # Minimal fallbacks to avoid import errors during test collection.
    db = None
    mail = None
    babel = None
    cache = None

__all__ = ["db", "mail", "babel", "cache"]
