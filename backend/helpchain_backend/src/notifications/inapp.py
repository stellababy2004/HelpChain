from datetime import datetime, timedelta

from backend.extensions import db
from backend.helpchain_backend.src.models import VolunteerRequestState
from backend.models import Notification, RequestActivity
from flask import url_for

NUDGE_COOLDOWN_HOURS = 6


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


def mark_request_seen_for_volunteer(
    request_id: int,
    volunteer_id: int,
    seen_at: datetime | None = None,
    *,
    commit: bool = True,
) -> bool:
    """
    Idempotent canonical seen marker.
    Updates VolunteerRequestState.seen_at only when a state row exists and seen_at is NULL.
    """
    if not request_id or not volunteer_id:
        return False

    row = VolunteerRequestState.query.filter_by(
        request_id=request_id, volunteer_id=volunteer_id
    ).first()
    if not row:
        return False

    if getattr(row, "seen_at", None) is not None:
        return False

    row.seen_at = seen_at or datetime.utcnow()
    if commit:
        db.session.commit()
    return True


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

    if n.request_id and mark_request_seen_for_volunteer(
        request_id=n.request_id,
        volunteer_id=volunteer_id,
        seen_at=ts,
        commit=False,
    ):
        changed = True

    if changed:
        db.session.commit()

    if n.request_id:
        return url_for("main.volunteer_request_details", req_id=n.request_id), n.request_id
    return url_for("main.volunteer_notifications"), None


def send_nudge_notification(
    request_id: int,
    volunteer_id: int,
    *,
    actor_admin_id: int | None = None,
    now: datetime | None = None,
) -> bool:
    """
    Send an admin nudge in-app notification with cooldown.
    Returns True when sent, False when suppressed by cooldown.
    """
    if not request_id or not volunteer_id:
        return False

    now = now or datetime.utcnow()
    cutoff = now - timedelta(hours=NUDGE_COOLDOWN_HOURS)

    existing = (
        Notification.query.filter(Notification.volunteer_id == volunteer_id)
        .filter(Notification.request_id == request_id)
        .filter(Notification.type == "admin_nudge")
        .order_by(Notification.created_at.desc())
        .first()
    )
    if existing and existing.created_at and existing.created_at >= cutoff:
        return False

    if existing:
        # Reuse row due unique (volunteer_id, type, request_id) constraint.
        existing.title = "Reminder: please check this request"
        existing.body = "An admin asked you to review this request and respond when you can."
        existing.created_at = now
        existing.is_read = False
        existing.read_at = None
    else:
        db.session.add(
            Notification(
                volunteer_id=volunteer_id,
                request_id=request_id,
                type="admin_nudge",
                title="Reminder: please check this request",
                body="An admin asked you to review this request and respond when you can.",
                is_read=False,
                read_at=None,
                created_at=now,
            )
        )

    try:
        db.session.add(
            RequestActivity(
                request_id=request_id,
                actor_admin_id=actor_admin_id,
                volunteer_id=volunteer_id,
                action="admin_nudge_sent",
                created_at=now,
            )
        )
    except Exception:
        pass

    db.session.commit()
    return True
