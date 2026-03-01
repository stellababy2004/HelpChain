from functools import wraps

from flask import jsonify, request
from sqlalchemy import and_

from .jwt_utils import decode_token


def require_access_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_token"}), 401
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token, "access")
        except Exception:
            return jsonify({"error": "invalid_token"}), 401
        request.jwt_payload = payload
        return fn(*args, **kwargs)

    return wrapper


# --- Notification access policies ---
def can_view_notification(user, notification) -> bool:
    """Volunteer can only see/open their own notifications.

    We support both ownership styles:
    - Legacy/canonical: `notification.volunteer_id` (Volunteer.id)
    - Newer owner field: `notification.user_id` (Volunteer.user_id)
    """
    if not user or not notification:
        return False

    volunteer_id = getattr(user, "id", None)
    if not volunteer_id:
        return False

    notif_volunteer_id = getattr(notification, "volunteer_id", None)
    if notif_volunteer_id is not None:
        return notif_volunteer_id == volunteer_id

    notif_user_id = getattr(notification, "user_id", None)
    if notif_user_id is None:
        return False

    # Prefer linking through Volunteer.user_id when present.
    volunteer_user_id = getattr(user, "user_id", None)
    if volunteer_user_id is not None:
        return notif_user_id == volunteer_user_id

    # Fallback: some fixtures/codepaths may reuse the same id space.
    return notif_user_id == volunteer_id


# --- Request access policies ---
def can_view_request(user, req, db):
    """
    Allow view if:
    - request is assigned to this user (volunteer), OR
    - user has ANY interest row for this request (pending/approved/rejected, etc.).
    """
    if not user or not req or not getattr(user, "id", None):
        return False

    # Assigned volunteer
    if getattr(req, "assigned_volunteer_id", None) == getattr(user, "id", None):
        return True

    # Approved interest
    from .models.volunteer_interest import VolunteerInterest

    approved_interest_exists = (
        db.session.query(VolunteerInterest.id)
        .filter(
            and_(
                VolunteerInterest.request_id == req.id,
                VolunteerInterest.volunteer_id == user.id,
            )
        )
        .first()
        is not None
    )

    return approved_interest_exists
