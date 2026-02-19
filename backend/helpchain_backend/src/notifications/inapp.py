from datetime import datetime

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
