from datetime import datetime

from flask import url_for

from backend.extensions import db
from backend.models import Notification
from backend.helpchain_backend.src.models import VolunteerRequestState


def touch_request_state_notified(
    volunteer_id: int,
    request_id: int | None,
    notified_at: datetime | None = None,
    *,
    commit: bool = True,
) -> None:
    """
    Persist notification timestamp into VolunteerRequestState.
    Safe fallback: no-op when schema isn't migrated yet.
    """
    if not volunteer_id or not request_id:
        return
    ts = notified_at or datetime.utcnow()
    try:
        row = VolunteerRequestState.query.filter_by(
            volunteer_id=volunteer_id, request_id=request_id
        ).first()
        if not row:
            row = VolunteerRequestState(
                volunteer_id=volunteer_id,
                request_id=request_id,
                notified_at=ts,
            )
            db.session.add(row)
        else:
            prev = getattr(row, "notified_at", None)
            if prev is None or prev > ts:
                row.notified_at = ts
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()


def touch_request_state_seen(
    volunteer_id: int,
    request_id: int | None,
    seen_at: datetime | None = None,
    *,
    commit: bool = True,
) -> None:
    """
    Persist "seen" timestamp into VolunteerRequestState.
    Safe fallback: no-op when schema isn't migrated yet.
    """
    if not volunteer_id or not request_id:
        return
    ts = seen_at or datetime.utcnow()
    try:
        row = VolunteerRequestState.query.filter_by(
            volunteer_id=volunteer_id, request_id=request_id
        ).first()
        if not row:
            row = VolunteerRequestState(
                volunteer_id=volunteer_id,
                request_id=request_id,
                seen_at=ts,
            )
            db.session.add(row)
        else:
            prev = getattr(row, "seen_at", None)
            if prev is None or prev > ts:
                row.seen_at = ts
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()


def ensure_new_match_notifications(volunteer_id: int, request_rows) -> int:
    """
    Create at most one in-app notification per (volunteer, request) for type 'new_match'.
    Idempotent via unique constraint; returns number of created rows.
    """
    if not volunteer_id or not request_rows:
        return 0

    created = 0
    for r in request_rows:
        req_id = getattr(r, "id", None)
        ts = datetime.utcnow()
        notif = Notification(
            volunteer_id=volunteer_id,
            type="new_match",
            request_id=req_id,
            title=getattr(r, "title", "") or "New matching request",
            body=getattr(r, "description", None) or getattr(r, "message", None) or "",
            created_at=ts,
        )
        db.session.add(notif)
        touch_request_state_notified(
            volunteer_id=volunteer_id,
            request_id=req_id,
            notified_at=ts,
            commit=False,
        )
        try:
            db.session.commit()
            created += 1
        except Exception:
            db.session.rollback()
            # likely unique constraint hit; keep state timestamp aligned.
            try:
                existing = (
                    Notification.query.filter_by(
                        volunteer_id=volunteer_id, type="new_match", request_id=req_id
                    )
                    .order_by(Notification.created_at.asc())
                    .first()
                )
                if existing:
                    touch_request_state_notified(
                        volunteer_id=volunteer_id,
                        request_id=req_id,
                        notified_at=existing.created_at,
                        commit=True,
                    )
            except Exception:
                db.session.rollback()
    return created


def mark_notification_opened(notif_id: int, volunteer_id: int) -> tuple[str, int | None]:
    """
    Canonical open path for volunteer in-app notifications.
    Idempotently marks notification as read/seen and sets request_state.seen_at.
    Returns (redirect_url, request_id).
    """
    owner_col = getattr(Notification, "volunteer_id", None) or getattr(
        Notification, "user_id", None
    )
    if owner_col is None:
        raise RuntimeError("Notification owner column is missing")

    n = Notification.query.filter(owner_col == volunteer_id, Notification.id == notif_id).first()
    if not n:
        raise LookupError("Notification not found")

    ts = datetime.utcnow()
    changed = False

    if hasattr(n, "is_read") and not bool(getattr(n, "is_read", False)):
        n.is_read = True
        changed = True

    if hasattr(n, "read_at") and getattr(n, "read_at", None) is None:
        n.read_at = ts
        changed = True

    if hasattr(n, "seen_at") and getattr(n, "seen_at", None) is None:
        n.seen_at = ts
        changed = True

    if hasattr(n, "status") and getattr(n, "status", None) == "UNREAD":
        n.status = "READ"
        changed = True

    if n.request_id:
        touch_request_state_seen(
            volunteer_id=volunteer_id,
            request_id=n.request_id,
            seen_at=ts,
            commit=False,
        )
        changed = True

    if changed:
        db.session.commit()

    if n.request_id:
        return url_for("main.volunteer_request_details", req_id=n.request_id), n.request_id
    return url_for("main.volunteer_notifications"), None
