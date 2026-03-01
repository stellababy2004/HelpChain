from backend.extensions import db
from ..models import Notification


def notify_new_match(volunteer, request):
    """Create a single in-app notification for a new match (idempotent via unique constraint)."""
    if not volunteer or not request:
        return False
    notif = Notification(
        volunteer_id=volunteer.id,
        type="match",
        request_id=request.id,
    )
    db.session.add(notif)
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False
