import secrets
from datetime import UTC, datetime, timedelta, timezone

import jwt  # PyJWT
from flask import current_app


def _now():
    return datetime.now(UTC)


def new_jti():
    return secrets.token_hex(16)  # 32 hex chars


def encode_access_token(user_id: int) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iss": current_app.config["JWT_ISSUER"],
        "aud": current_app.config["JWT_AUDIENCE"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=current_app.config["JWT_ACCESS_TTL_SECONDS"])).timestamp()),
        "jti": new_jti(),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALG"])


def encode_refresh_token(user_id: int, jti: str, exp_dt: datetime) -> str:
    payload = {
        "sub": str(user_id),
        "typ": "refresh",
        "iss": current_app.config["JWT_ISSUER"],
        "aud": current_app.config["JWT_AUDIENCE"],
        "iat": int(_now().timestamp()),
        "exp": int(exp_dt.timestamp()),
        "jti": jti,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALG"])


def decode_token(token: str, expected_type: str):
    payload = jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALG"]],
        audience=current_app.config["JWT_AUDIENCE"],
        issuer=current_app.config["JWT_ISSUER"],
        leeway=current_app.config.get("JWT_CLOCK_SKEW_SECONDS", 0),
        options={"require": ["exp", "iat", "iss", "aud", "sub", "typ", "jti"]},
    )
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload
