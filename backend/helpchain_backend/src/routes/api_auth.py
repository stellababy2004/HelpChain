from datetime import datetime, timedelta, timezone
import time

import jwt
from flask import Blueprint, current_app, jsonify, request, g
from werkzeug.security import check_password_hash

from ..models import AdminUser
from ..security.api_authz import require_api_auth

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


def _jwt_secret():
    return current_app.config.get("JWT_SECRET_KEY") or current_app.config.get("SECRET_KEY")


def _make_token(admin_user: AdminUser) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_user.id),
        "role": getattr(admin_user, "role", None),
        "is_admin": bool(getattr(admin_user, "is_admin", False)),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
        "iss": "helpchain",
        "typ": "access",
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


# Very lightweight in-memory throttle: 10 attempts / 60s per IP (dev-friendly)
_login_attempts = {}
_MAX_ATTEMPTS = 10
_WINDOW_SEC = 60


def _too_many_attempts(ip: str) -> bool:
    now = time.time()
    window = _login_attempts.get(ip, [])
    window = [ts for ts in window if now - ts < _WINDOW_SEC]
    if len(window) >= _MAX_ATTEMPTS:
        _login_attempts[ip] = window
        return True
    window.append(now)
    _login_attempts[ip] = window
    return False


@api_auth_bp.post("/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if _too_many_attempts(ip):
        return jsonify({"error": "Too many attempts, try again later"}), 429

    user = AdminUser.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401

    token = _make_token(user)
    return (
        jsonify(
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": 8 * 3600,
                "role": getattr(user, "role", None),
                "is_admin": bool(getattr(user, "is_admin", False)),
            }
        ),
        200,
    )


@api_auth_bp.get("/me")
@require_api_auth
def api_me():
    claims = getattr(g, "api_claims", {}) or {}
    return jsonify(
        {
            "user_id": claims.get("sub"),
            "role": claims.get("role"),
            "is_admin": bool(claims.get("is_admin", False)),
            "iat": claims.get("iat"),
            "exp": claims.get("exp"),
            "iss": claims.get("iss"),
        }
    ), 200
