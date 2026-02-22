from __future__ import annotations

from datetime import datetime

from flask import request as flask_request
from flask_login import current_user
from sqlalchemy.orm import Session

from backend.extensions import db
from backend.models import ActivityLog


def log_activity(
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    message: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    meta: dict | None = None,
    actor_user_id: int | None = None,
    actor_email: str | None = None,
    flush: bool = False,
    persist: bool = False,
):
    """
    Centralized audit trail writer.
    Caller owns transaction/commit.
    """
    if actor_user_id is None:
        try:
            actor_user_id = getattr(current_user, "id", None)
        except Exception:
            actor_user_id = None

    if actor_email is None:
        try:
            actor_email = (
                getattr(current_user, "email", None)
                or getattr(current_user, "username", None)
            )
        except Exception:
            actor_email = None

    enriched_meta = dict(meta or {})
    try:
        enriched_meta.setdefault(
            "ip",
            flask_request.headers.get("X-Forwarded-For", flask_request.remote_addr),
        )
        enriched_meta.setdefault("ua", flask_request.headers.get("User-Agent"))
        enriched_meta.setdefault("path", flask_request.path)
        enriched_meta.setdefault("method", flask_request.method)
    except Exception:
        pass

    payload = {
        "entity_type": entity_type,
        "entity_id": int(entity_id),
        "actor_user_id": actor_user_id,
        "actor_email": actor_email,
        "action": action,
        "message": message,
        "old_value": old_value,
        "new_value": new_value,
        "meta": enriched_meta,
        "created_at": datetime.utcnow(),
    }

    if persist:
        bind = db.session.get_bind()
        with bind.begin() as conn:
            conn.execute(ActivityLog.__table__.insert().values(**payload))
        return None

    row = ActivityLog(**payload)
    db.session.add(row)
    if flush:
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
            raise
    return row


# Backward-compatible wrappers used in a few legacy modules.
def log_admin_action(
    db: Session,
    actor_user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str | None = None,
    metadata: dict | None = None,
):
    row = ActivityLog(
        entity_type=(target_type or "admin"),
        entity_id=int(target_id or 0),
        actor_user_id=actor_user_id,
        action=action,
        message=outcome,
        meta=metadata or {},
    )
    db.add(row)
    db.commit()
    return row


def log_audit(
    session: Session,
    *,
    actor_user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str | None = None,
    metadata: dict | None = None,
):
    row = ActivityLog(
        entity_type=(target_type or "audit"),
        entity_id=int(target_id or 0),
        actor_user_id=actor_user_id,
        action=action,
        message=outcome,
        meta=metadata or {},
    )
    session.add(row)
    session.commit()
    return row
