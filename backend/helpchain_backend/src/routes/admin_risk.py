from __future__ import annotations

from flask import Blueprint, jsonify

from backend.helpchain_backend.src.services.risk_engine import compute_case_risk
from .admin import admin_required, admin_required_404


admin_risk_bp = Blueprint("admin_risk_api", __name__, url_prefix="/admin/api")


@admin_risk_bp.get("/cases/<int:case_id>/risk")
@admin_required
def admin_case_risk(case_id: int):
    admin_required_404()
    result = compute_case_risk(case_id)
    if result is None:
        return jsonify({"error": "case_not_found"}), 404
    return jsonify(result)
