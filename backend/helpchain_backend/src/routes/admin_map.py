from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.extensions import db
from backend.helpchain_backend.src.models import Case
from backend.helpchain_backend.src.services.risk_engine import compute_case_risk
from .admin import (
    _current_structure_id,
    _is_global_admin,
    admin_required,
    admin_required_404,
    admin_role_required,
)


admin_map_bp = Blueprint("admin_map_api", __name__, url_prefix="/admin")


def _safe_iso(dt) -> str | None:
    if isinstance(dt, datetime):
        return dt.replace(tzinfo=None).isoformat(timespec="seconds")
    return None


def _risk_level_from_score(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _valid_coordinates(lat_value, lng_value) -> tuple[float, float] | None:
    try:
        lat = float(lat_value)
        lng = float(lng_value)
    except Exception:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return lat, lng


def _scope_case_query(query):
    if _is_global_admin():
        return query

    try:
        return query.filter(Case.structure_id == _current_structure_id())
    except Exception:
        current_structure = getattr(current_user, "structure_id", None)
        if current_structure is not None:
            return query.filter(Case.structure_id == int(current_structure))
        return query


def _serialize_risk_map_item(case: Case) -> dict[str, object]:
    request_row = getattr(case, "request", None)
    coords = _valid_coordinates(
        getattr(case, "latitude", None),
        getattr(case, "longitude", None),
    )
    if coords is None:
        return {}

    risk_score = int(getattr(case, "risk_score", None) or 0)
    title = (
        getattr(request_row, "title", None)
        or getattr(request_row, "city", None)
        or f"Case #{case.id}"
    )
    return {
        "id": int(case.id),
        "title": str(title),
        "latitude": coords[0],
        "longitude": coords[1],
        "risk_level": _risk_level_from_score(risk_score),
        "risk_score": risk_score,
        "category": str(getattr(request_row, "category", None) or ""),
        "status": str(getattr(case, "status", None) or ""),
        "updated_at": _safe_iso(
            getattr(case, "updated_at", None) or getattr(case, "created_at", None)
        ),
        "city": str(getattr(request_row, "city", None) or ""),
        "source_type": "case",
        "request_id": int(getattr(case, "request_id", 0) or 0),
    }


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


@admin_map_bp.get("/api/risk-map")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_risk_map_api():
    admin_required_404()
    try:
        query = (
            Case.query.options(joinedload(Case.request))
            .filter(Case.latitude.isnot(None), Case.longitude.isnot(None))
            .filter(Case.latitude.between(-90, 90))
            .filter(Case.longitude.between(-180, 180))
            .order_by(Case.risk_score.desc(), Case.updated_at.desc(), Case.id.desc())
        )
        cases = _scope_case_query(query).limit(1000).all()
        items = [
            item for item in (_serialize_risk_map_item(case) for case in cases) if item
        ]
        return jsonify(
            {
                "status": "ok",
                "items": items,
                "default_center": {"lat": 46.603354, "lng": 1.888334, "zoom": 6},
                "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(
                    timespec="seconds"
                ),
            }
        )
    except Exception:
        current_app.logger.exception("admin_risk_map_api_failed")
        return (
            jsonify(
                {
                    "status": "error",
                    "items": [],
                    "message": "risk_map_data_unavailable",
                    "default_center": {"lat": 46.603354, "lng": 1.888334, "zoom": 6},
                }
            ),
            500,
        )


@admin_map_bp.get("/api/cases/map")
@admin_required
def admin_cases_map_api():
    admin_required_404()
    rows = _load_cases_with_geo()
    payload = []
    for row in rows:
        risk = compute_case_risk(int(row.id)) or {}
        risk_level = risk.get("risk_level", "low")
        if risk_level == "critical":
            risk_level = "high"
        payload.append(
            {
                "id": int(row.id),
                "lat": float(row.latitude),
                "lng": float(row.longitude),
                "status": str(row.status or "open"),
                "risk_level": risk_level,
                "created_at": _safe_iso(row.created_at),
            }
        )
    return jsonify({"cases": payload})


@admin_map_bp.get("/cases/map")
@admin_required
def admin_cases_map_page():
    admin_required_404()
    return render_template("admin_cases_map.html")