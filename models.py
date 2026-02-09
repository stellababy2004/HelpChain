# Compatibility shim to expose `backend.models` at the top level
# so imports like `from models import AdminUser` work when running
# scripts or tests from the repository root.

try:
    from backend.models import AdminUser, HelpRequest, User, Volunteer  # type: ignore # noqa: F403
except Exception:
    # Minimal fallback to avoid hard import failure during early collection.
    pass
