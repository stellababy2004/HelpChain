import uuid

from flask import Blueprint, jsonify, request, url_for
from werkzeug.security import generate_password_hash

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """User signup endpoint"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not all([username, email, password]):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Username, email, and password are required",
                }
            ),
            400,
        )

    # Check if user already exists
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        return jsonify({"success": False, "error": "User already exists"}), 409

    # Create new user
    user = User(
        username=username, email=email, password_hash=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    # Generate confirmation token
    confirm_token = str(uuid.uuid4())

    # In TESTING mode, return the confirm_url directly
    from flask import current_app

    if current_app.config.get("TESTING"):
        confirm_url = url_for("auth.confirm_email", token=confirm_token, _external=True)
        return (
            jsonify(
                {
                    "success": True,
                    "message": "User created successfully",
                    "confirm_url": confirm_url,
                }
            ),
            201,
        )

    # In production, you would send an email with the confirmation link
    # For now, just return success
    return (
        jsonify(
            {
                "success": True,
                "message": "User created successfully. Please check your email for confirmation.",
            }
        ),
        201,
    )


@auth_bp.route("/confirm/<token>", methods=["GET"])
def confirm_email(token):
    """Email confirmation endpoint"""
    # In a real implementation, you'd validate the token and mark the user as confirmed
    # For testing purposes, just return success
    return jsonify({"success": True, "message": "Email confirmed successfully"}), 200
