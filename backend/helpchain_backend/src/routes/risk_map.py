from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import func, inspect

from backend.extensions import db
from backend.helpchain_backend.src.models import Case
from backend.helpchain_backend.src.services.risk_prediction import predict_risk
from backend.helpchain_backend.src.services.early_warning import detect_ews
from .admin import admin_required, admin_required_404


risk_map_bp = Blueprint("risk_map_api", __name__)


def get_risk_color(score: int) -> str:
    if score >= 80:
        return "red"
    if score >= 60:
        return "orange"
    if score >= 30:
        return "yellow"
    return "green"


def _cases_has_geo_columns() -> bool:
    try:
        bind = db.session.get_bind()
        if not bind:
            return False
        inspector = inspect(bind)
        if "cases" not in inspector.get_table_names():
            return False
        columns = {col["name"] for col in inspector.get_columns("cases")}
        return "latitude" in columns and "longitude" in columns
    except Exception:
        return False


@risk_map_bp.get("/api/cases/map")
def cases_map_api():
    structure_raw = (request.args.get("structure_id") or "").strip()
    try:
        structure_id = int(structure_raw)
    except Exception:
        structure_id = None

    if not structure_id:
        return jsonify({"error": "structure_id is required"}), 400

    bbox_raw = (request.args.get("bbox") or "").strip()
    bbox = None
    if bbox_raw:
        parts = [p.strip() for p in bbox_raw.split(",") if p.strip()]
        if len(parts) != 4:
            return jsonify({"error": "bbox must have 4 comma-separated values"}), 400
        try:
            min_lat, min_lon, max_lat, max_lon = [float(p) for p in parts]
        except Exception:
            return jsonify({"error": "bbox must contain valid floats"}), 400
        if min_lat > max_lat or min_lon > max_lon:
            return jsonify({"error": "bbox min values must be <= max values"}), 400
        bbox = (min_lat, min_lon, max_lat, max_lon)

    if not _cases_has_geo_columns():
        return jsonify({"type": "FeatureCollection", "features": []})

    cases_query = (
        Case.query
        .filter(Case.structure_id == structure_id)
        .filter(Case.latitude.isnot(None), Case.longitude.isnot(None))
        .filter(Case.latitude.between(-90, 90))
        .filter(Case.longitude.between(-180, 180))
        .order_by(Case.risk_score.desc())
    )

    if bbox:
        min_lat, min_lon, max_lat, max_lon = bbox
        cases_query = cases_query.filter(
            Case.latitude.between(min_lat, max_lat),
            Case.longitude.between(min_lon, max_lon),
        )

    cases = cases_query.limit(1000).all()

    features = []
    for case in cases:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(case.longitude),
                        float(case.latitude),
                    ],
                },
                "properties": {
                    "case_id": int(case.id),
                    "risk_score": int(case.risk_score or 0),
                    "status": str(case.status or ""),
                    "priority": str(case.priority or ""),
                },
            }
        )

    return jsonify({"type": "FeatureCollection", "features": features})


@risk_map_bp.get("/api/cases/grid")
def cases_grid_api():
    structure_raw = (request.args.get("structure_id") or "").strip()
    try:
        structure_id = int(structure_raw)
    except Exception:
        structure_id = None

    if not structure_id:
        return jsonify({"error": "structure_id is required"}), 400

    bbox_raw = (request.args.get("bbox") or "").strip()
    if not bbox_raw:
        return jsonify({"error": "bbox is required"}), 400
    parts = [p.strip() for p in bbox_raw.split(",") if p.strip()]
    if len(parts) != 4:
        return jsonify({"error": "bbox must have 4 comma-separated values"}), 400
    try:
        min_lat, min_lon, max_lat, max_lon = [float(p) for p in parts]
    except Exception:
        return jsonify({"error": "bbox must contain valid floats"}), 400
    if min_lat > max_lat or min_lon > max_lon:
        return jsonify({"error": "bbox min values must be <= max values"}), 400

    zoom_raw = (request.args.get("zoom") or "").strip()
    try:
        zoom = int(zoom_raw)
    except Exception:
        zoom = None

    if zoom is None:
        grid_size = 0.05
    elif zoom <= 8:
        grid_size = 0.2
    elif zoom <= 12:
        grid_size = 0.05
    else:
        grid_size = 0.01

    if not _cases_has_geo_columns():
        return jsonify({"cells": []})

    cell_lat = (func.round(Case.latitude / grid_size, 0) * grid_size).label("cell_lat")
    cell_lon = (func.round(Case.longitude / grid_size, 0) * grid_size).label("cell_lon")
    avg_risk = func.avg(func.coalesce(Case.risk_score, 0)).label("avg_risk")
    max_risk = func.max(func.coalesce(Case.risk_score, 0)).label("max_risk")
    count_cases = func.count(Case.id).label("count_cases")

    query = (
        db.session.query(cell_lat, cell_lon, count_cases, avg_risk, max_risk)
        .filter(Case.structure_id == structure_id)
        .filter(Case.latitude.isnot(None), Case.longitude.isnot(None))
        .filter(Case.latitude.between(-90, 90))
        .filter(Case.longitude.between(-180, 180))
        .filter(Case.latitude.between(min_lat, max_lat))
        .filter(Case.longitude.between(min_lon, max_lon))
        .group_by(cell_lat, cell_lon)
        .order_by(count_cases.desc())
        .limit(500)
    )

    cells = []
    for row in query.all():
        cells.append(
            {
                "lat": float(row.cell_lat),
                "lon": float(row.cell_lon),
                "count": int(row.count_cases or 0),
                "avg_risk": int(round(row.avg_risk or 0)),
                "max_risk": int(row.max_risk or 0),
            }
        )

    return jsonify({"cells": cells})


@risk_map_bp.get("/api/cases/predict")
def cases_predict_api():
    structure_raw = (request.args.get("structure_id") or "").strip()
    try:
        structure_id = int(structure_raw)
    except Exception:
        structure_id = None

    if not structure_id:
        return jsonify({"error": "structure_id is required"}), 400

    bbox_raw = (request.args.get("bbox") or "").strip()
    if not bbox_raw:
        return jsonify({"error": "bbox is required"}), 400
    parts = [p.strip() for p in bbox_raw.split(",") if p.strip()]
    if len(parts) != 4:
        return jsonify({"error": "bbox must have 4 comma-separated values"}), 400
    try:
        min_lat, min_lon, max_lat, max_lon = [float(p) for p in parts]
    except Exception:
        return jsonify({"error": "bbox must contain valid floats"}), 400
    if min_lat > max_lat or min_lon > max_lon:
        return jsonify({"error": "bbox min values must be <= max values"}), 400

    zoom_raw = (request.args.get("zoom") or "").strip()
    try:
        zoom = int(zoom_raw)
    except Exception:
        zoom = None

    cells = predict_risk(structure_id, (min_lat, min_lon, max_lat, max_lon), zoom)
    return jsonify({"cells": cells})


@risk_map_bp.get("/api/cases/ews")
def cases_ews_api():
    structure_raw = (request.args.get("structure_id") or "").strip()
    try:
        structure_id = int(structure_raw)
    except Exception:
        structure_id = None

    if not structure_id:
        return jsonify({"error": "structure_id is required"}), 400

    bbox_raw = (request.args.get("bbox") or "").strip()
    if not bbox_raw:
        return jsonify({"error": "bbox is required"}), 400
    parts = [p.strip() for p in bbox_raw.split(",") if p.strip()]
    if len(parts) != 4:
        return jsonify({"error": "bbox must have 4 comma-separated values"}), 400
    try:
        min_lat, min_lon, max_lat, max_lon = [float(p) for p in parts]
    except Exception:
        return jsonify({"error": "bbox must contain valid floats"}), 400
    if min_lat > max_lat or min_lon > max_lon:
        return jsonify({"error": "bbox min values must be <= max values"}), 400

    alerts = detect_ews(structure_id, (min_lat, min_lon, max_lat, max_lon))
    return jsonify({"alerts": alerts})


@risk_map_bp.get("/admin/risk-map")
@admin_required
def admin_risk_map():
    admin_required_404()
    structure_id = request.args.get("structure_id")
    if not structure_id:
        structure_id = getattr(current_user, "structure_id", None)
    return render_template("admin/risk_map.html", structure_id=structure_id or "")
