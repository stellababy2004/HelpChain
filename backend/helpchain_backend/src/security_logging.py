import json
import logging
from datetime import UTC, datetime

from flask import has_request_context, request

from backend.extensions import db

logger = logging.getLogger("security")


def _sha256_hex(value: str | None) -> str | None:
    if not value:
        return None
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def log_security_event(event_type: str, **fields):
    """
    Minimal, dependency-free security logger.
    Keeps app startup resilient in constrained deploy environments.
    """
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        **fields,
    }
    logger.info("[SECURITY] %s", payload)
    try:
        from backend.models import SecurityEvent

        meta = fields.get("meta")
        req_ip = None
        req_route = None
        req_method = None
        req_ua = None
        if has_request_context():
            req_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            req_ip = req_ip or request.remote_addr
            req_route = request.path
            req_method = request.method
            req_ua = request.headers.get("User-Agent")

        values = {
            "event_type": (event_type or "")[:64],
            "actor_type": (fields.get("actor_type") or "anonymous")[:32],
            "actor_id": fields.get("actor_id"),
            "ip": (fields.get("ip") or req_ip or None),
            "email_hash": (fields.get("email_hash") or None),
            "route": (fields.get("route") or req_route or None),
            "method": (fields.get("method") or req_method or None),
            "meta": (
                meta
                if isinstance(meta, dict)
                else {"value": meta}
                if meta is not None
                else None
            ),
            "meta_json": (
                json.dumps(meta, ensure_ascii=True, sort_keys=True, default=str)
                if meta is not None
                else None
            ),
            "ip_hash": _sha256_hex(fields.get("ip") or req_ip or None),
            "ua_hash": _sha256_hex(req_ua),
            "created_at": datetime.now(UTC),
        }
        with db.engine.begin() as conn:
            conn.execute(SecurityEvent.__table__.insert().values(**values))
    except Exception:
        pass
