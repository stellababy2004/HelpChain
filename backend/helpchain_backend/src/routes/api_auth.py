from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash

from backend.helpchain_backend.src.jwt_utils import (
    decode_token,
    encode_access_token,
    encode_refresh_token,
    new_jti,
)

from ..authz import require_access_token
from ..extensions import csrf, db, limiter
from ..models import AdminUser, RefreshToken
from ..security_logging import log_security_event

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")
csrf.exempt(api_auth_bp)


@api_auth_bp.post("/login")
@limiter.limit("10/minute;100/hour")
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = AdminUser.query.filter_by(username=username).first()
    if not user or not getattr(user, "is_active", False) or not check_password_hash(user.password_hash, password):
        log_security_event("auth_api_login_failed", meta={"reason": "invalid_credentials"})
        return jsonify({"error": "invalid_credentials"}), 401

    access = encode_access_token(user.id)

    # refresh token issuance + store
    refresh_jti = new_jti()
    exp_dt = datetime.utcnow() + timedelta(seconds=current_app.config["JWT_REFRESH_TTL_SECONDS"])
    db.session.add(RefreshToken(user_id=user.id, jti=refresh_jti, expires_at=exp_dt))
    db.session.commit()

    refresh = encode_refresh_token(user.id, refresh_jti, exp_dt)
    log_security_event("auth_api_login_success", actor_type="admin", actor_id=user.id)

    return jsonify({"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": current_app.config["JWT_ACCESS_TTL_SECONDS"]})


@api_auth_bp.post("/refresh")
@limiter.limit("30/hour")
def api_refresh():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("refresh_token") or ""
    try:
        payload = decode_token(token, "refresh")
    except Exception:
        log_security_event("auth_api_refresh_failed", meta={"reason": "invalid_token"})
        return jsonify({"error": "invalid_refresh"}), 401

    user_id = int(payload["sub"])
    jti = payload["jti"]

    row = RefreshToken.query.filter_by(jti=jti, user_id=user_id).first()
    if not row or not row.is_active():
        log_security_event("auth_api_refresh_failed", actor_type="admin", actor_id=user_id, meta={"reason": "revoked_or_expired"})
        return jsonify({"error": "refresh_revoked"}), 401

    # rotate: revoke old, issue new
    new_j = new_jti()
    exp_dt = datetime.utcnow() + timedelta(seconds=current_app.config["JWT_REFRESH_TTL_SECONDS"])

    row.revoked_at = datetime.utcnow()
    row.replaced_by_jti = new_j
    db.session.add(RefreshToken(user_id=user_id, jti=new_j, expires_at=exp_dt))
    db.session.commit()

    access = encode_access_token(user_id)
    refresh = encode_refresh_token(user_id, new_j, exp_dt)
    log_security_event("auth_api_refresh_success", actor_type="admin", actor_id=user_id)

    return jsonify({"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": current_app.config["JWT_ACCESS_TTL_SECONDS"]})


@api_auth_bp.post("/logout")
def api_logout():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("refresh_token") or ""
    try:
        payload = decode_token(token, "refresh")
    except Exception:
        return jsonify({"ok": True}), 200

    user_id = int(payload["sub"])
    jti = payload["jti"]
    row = RefreshToken.query.filter_by(jti=jti, user_id=user_id).first()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.session.commit()
    log_security_event("auth_api_logout", actor_type="admin", actor_id=user_id)
    return jsonify({"ok": True}), 200


@api_auth_bp.get("/me")
@require_access_token
def api_me():
    payload = getattr(request, "jwt_payload", {}) or {}
    return jsonify(
        {
            "user_id": payload.get("sub"),
            "typ": payload.get("typ"),
            "iat": payload.get("iat"),
            "exp": payload.get("exp"),
            "iss": payload.get("iss"),
            "aud": payload.get("aud"),
        }
    ), 200
