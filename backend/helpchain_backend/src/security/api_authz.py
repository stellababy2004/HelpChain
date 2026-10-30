from functools import wraps

from flask import g, jsonify

from ..admin_actor import BearerActorResolutionError, resolve_bearer_admin_actor


def require_api_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            actor = resolve_bearer_admin_actor()
        except BearerActorResolutionError as exc:
            return jsonify({"error": exc.message}), exc.status_code

        g.admin_actor = actor
        g.api_role = actor.role
        g.api_is_admin = actor.is_admin
        return fn(*args, **kwargs)

    return wrapper


def require_roles(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @require_api_auth
        def wrapper(*args, **kwargs):
            role = getattr(g, "api_role", None)
            is_admin = getattr(g, "api_is_admin", False)
            role_allowed = role in allowed_roles or (
                role == "superadmin" and "admin" in allowed_roles
            )
            if not is_admin or not role_allowed:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
