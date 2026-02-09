import hashlib
from typing import Any

from flask import current_app, request

from backend.extensions import db
from backend.models import SecurityEvent

# Keys we refuse to log (potential PII)
FORBIDDEN_META_KEYS = {
    "email",
    "phone",
    "name",
    "full_name",
    "address",
    "message",
    "description",
    "details",
    "content",
}


def _hash_with_secret(value: str | None) -> str | None:
    """Hash value with SECRET_KEY pepper; returns None when missing."""
    if not value:
        return None
    secret = (current_app.config.get("SECRET_KEY") or "missing-secret").encode("utf-8")
    data = value.encode("utf-8")
    return hashlib.sha256(secret + b"|" + data).hexdigest()[:32]


def _clean_meta(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not meta:
        return None
    cleaned: dict[str, Any] = {}
    for k, v in meta.items():
        if not k:
            continue
        key = str(k).strip().lower()
        if key in FORBIDDEN_META_KEYS:
            continue
        if isinstance(v, str):
            cleaned[key] = v[:120]
        elif isinstance(v, (int, float, bool)) or v is None:
            cleaned[key] = v
        else:
            cleaned[key] = str(v)[:120]
    return cleaned or None


def log_security_event(
    event_type: str,
    *,
    actor_type: str = "anonymous",
    actor_id: int | None = None,
    meta=None,
):
    """Best-effort security logging; never raises to callers."""
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
        ua = request.headers.get("User-Agent") or ""

        ev = SecurityEvent(
            event_type=event_type[:64],
            actor_type=(actor_type or "anonymous")[:32],
            actor_id=actor_id,
            ip_hash=_hash_with_secret(ip.split(",")[0].strip()),
            ua_hash=_hash_with_secret(ua),
            route=(request.path or "")[:128],
            method=(request.method or "")[:8],
            meta=_clean_meta(meta),
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
