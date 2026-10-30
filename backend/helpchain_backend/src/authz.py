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


def can_volunteer_access_request(volunteer, req, db) -> bool:
    """Strict, membership-aware authorization for a volunteer request.

    This guard is intentionally not wired into routes yet.  It fails closed
    unless the volunteer identity, its optional user account, the request's
    tenant, an approved membership, and a request-specific permission are all
    present.  Membership status is queried on every call, so an open session
    does not survive suspension or revocation.
    """
    if not volunteer or not req or not getattr(volunteer, "id", None):
        return False
    session = getattr(db, "session", db)
    if not bool(getattr(volunteer, "is_active", False)):
        return False

    user_id = getattr(volunteer, "user_id", None)
    if user_id is not None:
        from .models import User

        account = session.get(User, user_id)
        if account is None or not bool(getattr(account, "is_active", False)):
            return False

    structure_id = getattr(req, "structure_id", None)
    if structure_id is None:
        return False

    from backend.models import VolunteerStructureMembership

    membership_exists = (
        session.query(VolunteerStructureMembership.id)
        .filter_by(
            volunteer_id=volunteer.id,
            structure_id=structure_id,
            status="approved",
        )
        .first()
        is not None
    )
    if not membership_exists:
        return False

    assigned = getattr(req, "assigned_volunteer_id", None) == volunteer.id
    if assigned:
        return True

    from .models.volunteer_interest import VolunteerInterest

    approved_interest_exists = (
        session.query(VolunteerInterest.id)
        .filter_by(
            request_id=req.id,
            volunteer_id=volunteer.id,
            status="approved",
        )
        .first()
        is not None
    )
    return approved_interest_exists


def can_volunteer_discover_request(volunteer, req, db) -> bool:
    """Authorize the minimum visibility needed to discover a request.

    Discovery is intentionally narrower than request viewing: it requires a
    current approved membership and an open, non-archived, non-deleted,
    unassigned request, but does not require an approved interest yet.
    """
    if not volunteer or not req or not getattr(volunteer, "id", None):
        return False
    session = getattr(db, "session", db)
    if not bool(getattr(volunteer, "is_active", False)):
        return False

    user_id = getattr(volunteer, "user_id", None)
    if user_id is not None:
        from .models import User

        account = session.get(User, user_id)
        if account is None or not bool(getattr(account, "is_active", False)):
            return False

    structure_id = getattr(req, "structure_id", None)
    if structure_id is None:
        return False

    from backend.models import VolunteerStructureMembership

    approved = (
        session.query(VolunteerStructureMembership.id)
        .filter_by(
            volunteer_id=volunteer.id,
            structure_id=structure_id,
            status="approved",
        )
        .first()
        is not None
    )
    if not approved:
        return False

    return bool(
        (getattr(req, "status", "") or "").lower() == "open"
        and getattr(req, "assigned_volunteer_id", None) is None
        and not bool(getattr(req, "is_archived", False))
        and getattr(req, "deleted_at", None) is None
    )
