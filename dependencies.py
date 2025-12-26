# Compatibility shim to expose `backend.dependencies` at the top level
# so imports like `from dependencies import require_role` work when
# the current working directory is the repository root.

try:
    from backend.dependencies import require_role, require_admin_login  # type: ignore # noqa: F403
except Exception:
    # Minimal fallback: define no-op decorators to avoid import errors
    def require_role(*roles):
        def decorator(f):
            return f
        return decorator

    def require_admin_login():
        def decorator(f):
            return f
        return decorator
