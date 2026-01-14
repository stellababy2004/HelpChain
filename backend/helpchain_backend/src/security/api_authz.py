import jwt
from functools import wraps
from flask import current_app, jsonify, request, g


def _jwt_secret():
    return current_app.config.get("JWT_SECRET_KEY") or current_app.config.get("SECRET_KEY")


def _decode_token(token: str):
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=["HS256"],
        options={"require": ["exp", "iat", "sub"]},
    )


def require_api_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = auth.split(" ", 1)[1].strip()
        try:
            claims = _decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        g.api_claims = claims
        g.api_user_id = claims.get("sub")
        g.api_role = claims.get("role")
        g.api_is_admin = bool(claims.get("is_admin", False))
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
