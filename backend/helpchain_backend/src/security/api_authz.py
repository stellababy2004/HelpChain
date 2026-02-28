from functools import wraps

import jwt
from backend.helpchain_backend.src.jwt_utils import decode_token
from flask import g, jsonify, request

from ..extensions import db
from ..models import AdminUser, canonical_role


def require_api_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = auth.split(" ", 1)[1].strip()
        try:
            claims = decode_token(token, "access")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        g.api_claims = claims
        g.api_user_id = claims.get("sub")
        role = claims.get("role")
        is_admin = bool(claims.get("is_admin", False))

        # Load fresh role/is_admin from DB when possible (tokens may omit them)
        try:
            user = db.session.get(AdminUser, int(claims.get("sub")))
            if user:
                role = getattr(user, "role", role)
                is_admin = bool(getattr(user, "is_admin", is_admin))
        except Exception:
            pass

        g.api_role = role
        g.api_is_admin = is_admin or canonical_role(role) in ("admin", "superadmin")
        return fn(*args, **kwargs)

    return wrapper


def require_roles(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @require_api_auth
        def wrapper(*args, **kwargs):
            role = getattr(g, "api_role", None)
            is_admin = getattr(g, "api_is_admin", False)
            if is_admin:
                return fn(*args, **kwargs)
            if role not in allowed_roles:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
