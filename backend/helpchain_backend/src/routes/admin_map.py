from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, render_template
from sqlalchemy import select

from backend.extensions import db
from backend.helpchain_backend.src.models import Case
from backend.helpchain_backend.src.services.risk_engine import compute_case_risk
from .admin import admin_required, admin_required_404


admin_map_bp = Blueprint("admin_map_api", __name__, url_prefix="/admin")


def _safe_iso(dt) -> str | None:
    if isinstance(dt, datetime):
        return dt.replace(tzinfo=None).isoformat(timespec="seconds")
    return None


def _load_cases_with_geo():
    bind = db.session.get_bind()
    if not bind:
        return []
    metadata = db.MetaData()
    try:
        cases_table = db.Table("cases", metadata, autoload_with=bind)
    except Exception:
        return []
    if "latitude" not in cases_table.c or "longitude" not in cases_table.c:
        return []

    stmt = (
        select(
            cases_table.c.id,
            cases_table.c.latitude,
            cases_table.c.longitude,
            cases_table.c.status,
            cases_table.c.created_at,
        )
        .where(cases_table.c.latitude.isnot(None))
        .where(cases_table.c.longitude.isnot(None))
    )
    return db.session.execute(stmt).all()


@admin_map_bp.get("/api/cases/map")
@admin_required
def admin_cases_map_api():
    admin_required_404()
    rows = _load_cases_with_geo()
    payload = []
    for row in rows:
        risk = compute_case_risk(int(row.id)) or {}
        payload.append(
            {
                "id": int(row.id),
                "lat": float(row.latitude),
                "lng": float(row.longitude),
                "status": str(row.status or "open"),
                "risk_level": risk.get("risk_level", "low"),
                "created_at": _safe_iso(row.created_at),
            }
        )
    return jsonify({"cases": payload})


@admin_map_bp.get("/cases/map")
@admin_required
def admin_cases_map_page():
    admin_required_404()
    return render_template("admin_cases_map.html")
