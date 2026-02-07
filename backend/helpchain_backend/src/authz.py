from functools import wraps

from flask import request, jsonify

from backend.helpchain_backend.src.jwt_utils import decode_token


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
    """Volunteer can only see/open their own notifications."""
    if not user or not notification:
        return False
    return getattr(notification, "user_id", None) == getattr(user, "id", None)

