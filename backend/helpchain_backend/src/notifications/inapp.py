from backend.extensions import db
from backend.models import Notification


def ensure_new_match_notifications(volunteer_id: int, request_rows) -> int:
    """
    Create at most one in-app notification per (volunteer, request) for type 'new_match'.
    Idempotent via unique constraint; returns number of created rows.
    """
    if not volunteer_id or not request_rows:
        return 0

    created = 0
    for r in request_rows:
        notif = Notification(
            volunteer_id=volunteer_id,
            type="new_match",
            request_id=getattr(r, "id", None),
            title=getattr(r, "title", "") or "New matching request",
            body=getattr(r, "description", None) or getattr(r, "message", None) or "",
        )
        db.session.add(notif)
        try:
            db.session.commit()
            created += 1
        except Exception:
            db.session.rollback()
            # likely unique constraint hit; ignore
    return created
