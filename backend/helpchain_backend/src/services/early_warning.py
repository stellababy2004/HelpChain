from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case as sa_case, func

from backend.extensions import db
from backend.helpchain_backend.src.models import Case


def detect_ews(structure_id: int, bbox: tuple[float, float, float, float]):
    min_lat, min_lon, max_lat, max_lon = bbox
    grid_size = 0.05

    now = datetime.now(UTC)
    since_30 = now - timedelta(days=30)
    since_7 = now - timedelta(days=7)

    cell_lat = (func.round(Case.latitude / grid_size, 0) * grid_size).label("cell_lat")
    cell_lon = (func.round(Case.longitude / grid_size, 0) * grid_size).label("cell_lon")
    case_count_30d = func.count(Case.id).label("case_count_30d")
    case_count_7d = func.sum(
        sa_case((Case.created_at >= since_7, 1), else_=0)
    ).label("case_count_7d")
    avg_risk = func.avg(func.coalesce(Case.risk_score, 0)).label("avg_risk")
    critical_cases = func.sum(
        sa_case((Case.risk_score >= 90, 1), else_=0)
    ).label("critical_cases")

    rows = (
        db.session.query(
            cell_lat, cell_lon, case_count_30d, case_count_7d, avg_risk, critical_cases
        )
        .filter(Case.structure_id == structure_id)
        .filter(Case.created_at >= since_30)
        .filter(Case.latitude.isnot(None), Case.longitude.isnot(None))
        .filter(Case.latitude.between(-90, 90))
        .filter(Case.longitude.between(-180, 180))
        .filter(Case.latitude.between(min_lat, max_lat))
        .filter(Case.longitude.between(min_lon, max_lon))
        .group_by(cell_lat, cell_lon)
        .all()
    )

    alerts = []
    for row in rows:
        count_30 = int(row.case_count_30d or 0)
        count_7 = int(row.case_count_7d or 0)
        avg = float(row.avg_risk or 0)
        crit = int(row.critical_cases or 0)
        baseline = (count_30 / 4.0) if count_30 else 0.0
        growth_ratio = (count_7 / baseline) if baseline > 0 else (2.5 if count_7 > 0 else 0.0)

        should_alert = growth_ratio > 2 or crit >= 3 or avg >= 75
        if not should_alert:
            continue

        if avg >= 90:
            level = "emergency"
        elif avg >= 75:
            level = "high"
        else:
            level = "warning"

        alerts.append(
            {
                "lat": float(row.cell_lat),
                "lon": float(row.cell_lon),
                "level": level,
                "growth_ratio": round(growth_ratio, 2),
                "avg_risk": int(round(avg)),
                "critical_cases": int(crit),
            }
        )

    return alerts
