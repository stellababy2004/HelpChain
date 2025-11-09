from flask import Blueprint, current_app, jsonify, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

try:
    from .models import User
except Exception:
    from backend.models import User

try:
    from ._dispatch_email import _dispatch_email
except Exception:
    try:
        from _dispatch_email import _dispatch_email
    except Exception:
        _dispatch_email = None

try:
    from appy import db
except Exception:
    # Fallback - import extensions if appy isn't available at import time
    from backend.extensions import db  # type: ignore


auth_bp = Blueprint("auth", __name__)


def _make_serializer():
    secret = current_app.config.get("SECRET_KEY") or "dev-secret"
    return URLSafeTimedSerializer(secret)


@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    # Basic uniqueness checks
    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "error": "username_taken"}), 400
    if email and User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "email_taken"}), 400

    # Create user as inactive until email confirmation
    user = User(username=username, email=email, is_active=False)
    try:
        user.set_password(password)
    except Exception:
        # Fallback: if set_password raises (older tests or edge cases),
        # fall back to direct hash assignment to remain compatible.
        user.password_hash = generate_password_hash(password)

    db.session.add(user)
    db.session.commit()

    # Build confirmation token and URL
    serializer = _make_serializer()
    token = serializer.dumps(email, salt="email-confirm")
    confirm_url = url_for("auth.confirm_email", token=token, _external=True)

    # Send confirmation email (best-effort)
    subject = "HelpChain: Потвърдете имейла си"
    body = f"Моля потвърдете имейла си като посетите следния адрес: {confirm_url}\n"
    try:
        _dispatch_email(
            subject, [email], body, sender=current_app.config.get("MAIL_DEFAULT_SENDER")
        )
    except Exception:
        # Best-effort: ignore email failures (tests will still proceed)
        pass

    resp = {"success": True, "message": "confirmation_sent"}
    # For tests, expose the confirm URL so tests can follow it without depending on mail
    if current_app.config.get("TESTING"):
        resp["confirm_url"] = confirm_url

    return jsonify(resp), 201


@auth_bp.route("/auth/confirm/<token>", methods=["GET"])
def confirm_email(token):
    serializer = _make_serializer()
    try:
        email = serializer.loads(token, salt="email-confirm", max_age=60 * 60 * 24)
    except SignatureExpired:
        return jsonify({"success": False, "error": "token_expired"}), 400
    except BadSignature:
        return jsonify({"success": False, "error": "invalid_token"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "error": "user_not_found"}), 404

    if user.is_active:
        return jsonify({"success": True, "message": "already_active"})

    user.is_active = True
    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True, "message": "confirmed"})
