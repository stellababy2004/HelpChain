from collections import Counter

from flask import Blueprint, jsonify, render_template
from flask_login import current_user
from sqlalchemy import func

from backend.extensions import db
from backend.models import Request
from backend.helpchain_backend.src.models import ProfessionalLead

risk_api = Blueprint("risk_api", __name__)
DEFAULT_COORDS = (48.8566, 2.3522)
CITY_COORDS = {
    "boulogne-billancourt": (48.8352, 2.2411),
    "paris": (48.8566, 2.3522),
    "suresnes": (48.8714, 2.2293),
}
VISIBLE_PRO_STATUSES = {"imported", "qualified", "contacted", "approved"}


def _risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _resolve_coordinates(city: str | None, lat, lng) -> tuple[float, float]:
    # Keep DB coordinates when present.
    if lat is not None and lng is not None:
        return float(lat), float(lng)

    key = (city or "").strip().lower()
    if key in CITY_COORDS:
        return CITY_COORDS[key]

    return DEFAULT_COORDS


def _norm_city(city: str | None) -> str:
    return " ".join((city or "").strip().lower().replace("–", "-").split())


def _resolve_pro_coordinates(
    city: str | None,
    latitudes: list[float],
    longitudes: list[float],
) -> tuple[float, float]:
    if latitudes and longitudes:
        return (sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes))

    key = _norm_city(city)
    if key in CITY_COORDS:
        return CITY_COORDS[key]

    return DEFAULT_COORDS


@risk_api.route("/admin/professionals-map")
def professionals_map_page():
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "authentication_required"}), 401
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403
    return render_template("admin/professionals_map.html")


@risk_api.route("/admin/api/risk-map")
def risk_map():
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "authentication_required"}), 401
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403

    rows = (
        db.session.query(
            func.trim(Request.city).label("city"),
            func.avg(func.coalesce(Request.risk_score, 0)).label("avg_risk"),
            func.count(Request.id).label("cases"),
            func.avg(Request.latitude).label("lat"),
            func.avg(Request.longitude).label("lng"),
        )
        .filter(Request.city.isnot(None))
        .filter(func.trim(Request.city) != "")
        .group_by(func.trim(Request.city))
        .order_by(func.count(Request.id).desc())
        .all()
    )

    result = []
    for city, risk, count, lat, lng in rows:
        score = float(risk or 0.0)
        resolved_lat, resolved_lng = _resolve_coordinates(city, lat, lng)
        result.append(
            {
                "city": city,
                "avg_risk": round(score, 2),
                "cases": int(count or 0),
                "lat": resolved_lat,
                "lng": resolved_lng,
                "risk_level": _risk_level(score),
            }
        )

    return jsonify(result)


@risk_api.route("/admin/api/professionals-map")
def professionals_map():
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "authentication_required"}), 401
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403

    has_lat = hasattr(ProfessionalLead, "latitude")
    has_lng = hasattr(ProfessionalLead, "longitude")
    cols = [
        ProfessionalLead.city,
        ProfessionalLead.profession,
        ProfessionalLead.status,
    ]
    if has_lat and has_lng:
        cols.extend([ProfessionalLead.latitude, ProfessionalLead.longitude])

    rows = (
        db.session.query(*cols)
        .filter(ProfessionalLead.city.isnot(None))
        .filter(func.trim(ProfessionalLead.city) != "")
        .all()
    )

    grouped: dict[str, dict] = {}
    for row in rows:
        city = row[0]
        profession = row[1]
        status = row[2]
        lat = row[3] if has_lat and has_lng else None
        lng = row[4] if has_lat and has_lng else None
        st = (status or "").strip().lower()
        if st not in VISIBLE_PRO_STATUSES:
            continue

        key = _norm_city(city)
        if not key:
            continue
        bucket = grouped.setdefault(
            key,
            {
                "city": (city or "").strip(),
                "count": 0,
                "lat_values": [],
                "lng_values": [],
                "profession_counts": Counter(),
            },
        )

        bucket["count"] += 1
        if profession:
            bucket["profession_counts"][profession.strip()] += 1
        if lat is not None and lng is not None:
            try:
                bucket["lat_values"].append(float(lat))
                bucket["lng_values"].append(float(lng))
            except Exception:
                pass

    result = []
    for data in grouped.values():
        top_professions = [
            name for name, _cnt in data["profession_counts"].most_common(3)
        ]
        lat, lng = _resolve_pro_coordinates(
            data["city"], data["lat_values"], data["lng_values"]
        )
        result.append(
            {
                "city": data["city"] or "Paris",
                "count": int(data["count"]),
                "lat": float(lat),
                "lng": float(lng),
                "top_professions": top_professions,
            }
        )

    result.sort(key=lambda item: (-item["count"], item["city"].lower()))
    return jsonify(result)
