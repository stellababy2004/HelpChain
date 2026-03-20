from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_mail import Message

from backend.extensions import mail
from backend.helpchain_backend.src.services.organization_service import (
    register_organization,
)


org_bp = Blueprint("organization_onboarding", __name__)


@org_bp.post("/create-organization")
def create_organization():
    payload = request.get_json(silent=True) or {}
    try:
        structure_id, admin_id = register_organization(payload)
    except ValueError as exc:
        code = str(exc)
        if code in {"organization_exists", "email_exists"}:
            return jsonify({"error": code}), 409
        return jsonify({"error": code}), 400

    base_url = (
        current_app.config.get("PUBLIC_BASE_URL")
        or request.host_url.rstrip("/")
    )
    login_url = f"{base_url}/admin/ops/login"
    dashboard_url = f"{base_url}/admin"
    password = payload.get("password")
    admin_email = payload.get("admin_email")

    body = (
        "Welcome to HelpChain\n\n"
        f"Login: {login_url}\n"
        f"Dashboard: {dashboard_url}\n"
        f"Temporary password: {password}\n"
    )

    try:
        msg = Message(
            subject="Welcome to HelpChain",
            recipients=[admin_email],
            body=body,
        )
        mail.send(msg)
    except Exception:
        current_app.logger.info("Welcome email send skipped/failed")

    return (
        jsonify(
            {
                "status": "created",
                "structure_id": structure_id,
                "message": "Organization successfully registered",
            }
        ),
        201,
    )
