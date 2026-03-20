from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case as sa_case, func

from backend.extensions import db
from backend.helpchain_backend.src.models import Case


def _grid_size_for_zoom(zoom: int | None) -> float:
    if zoom is None:
        return 0.05
    if zoom <= 8:
        return 0.2
    if zoom <= 12:
        return 0.05
    return 0.01


def predict_risk(structure_id: int, bbox: tuple[float, float, float, float], zoom: int | None):
    min_lat, min_lon, max_lat, max_lon = bbox
    grid_size = _grid_size_for_zoom(zoom)

    now = datetime.now(UTC)
    since_90 = now - timedelta(days=90)
    since_7 = now - timedelta(days=7)

    cell_lat = (func.round(Case.latitude / grid_size, 0) * grid_size).label("cell_lat")
    cell_lon = (func.round(Case.longitude / grid_size, 0) * grid_size).label("cell_lon")
    case_count = func.count(Case.id).label("case_count")
    avg_risk = func.avg(func.coalesce(Case.risk_score, 0)).label("avg_risk")
    recent_cases = func.sum(
        sa_case((Case.created_at >= since_7, 1), else_=0)
    ).label("recent_cases")

    rows = (
        db.session.query(cell_lat, cell_lon, case_count, avg_risk, recent_cases)
        .filter(Case.structure_id == structure_id)
        .filter(Case.created_at >= since_90)
        .filter(Case.latitude.isnot(None), Case.longitude.isnot(None))
        .filter(Case.latitude.between(-90, 90))
        .filter(Case.longitude.between(-180, 180))
        .filter(Case.latitude.between(min_lat, max_lat))
        .filter(Case.longitude.between(min_lon, max_lon))
        .group_by(cell_lat, cell_lon)
        .order_by(case_count.desc())
        .limit(500)
        .all()
    )

    cells = []
    periods = 90.0 / 7.0
    for row in rows:
        count = int(row.case_count or 0)
        avg = float(row.avg_risk or 0)
        recent = int(row.recent_cases or 0)
        historical_avg = count / periods if periods > 0 else 0.0
        if historical_avg <= 0:
            growth_rate = 0.0 if recent == 0 else 2.0
        else:
            growth_rate = recent / historical_avg

        predicted = avg + (growth_rate * 20.0)
        predicted = max(0.0, min(100.0, predicted))

        if growth_rate > 1.5:
            trend = "rising"
        elif growth_rate < 0.8:
            trend = "declining"
        else:
            trend = "stable"

        cells.append(
            {
                "lat": float(row.cell_lat),
                "lon": float(row.cell_lon),
                "predicted_risk": int(round(predicted)),
                "trend": trend,
                "avg_risk": int(round(avg)),
            }
        )

    return cells
