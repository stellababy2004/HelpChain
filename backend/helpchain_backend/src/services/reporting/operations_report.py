from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_

from backend.extensions import db
from backend.models import Request, Structure
from backend.helpchain_backend.src.services.sla_alerts import build_sla_alerts


CLOSED_STATUSES = {
    "done",
    "cancelled",
    "rejected",
    "canceled",
    "closed",
    "completed",
    "resolved",
    "archived",
}

RESOLVED_STATUSES = {
    "done",
    "closed",
    "completed",
    "resolved",
}


@dataclass(frozen=True)
class OperationalReportPeriod:
    start: datetime
    end: datetime


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _period_for_days(days: int, now: datetime | None = None) -> OperationalReportPeriod:
    safe_days = max(1, min(int(days or 7), 366))
    end = _normalize_dt(now) or _utc_now_naive()
    start = end - timedelta(days=safe_days)
    return OperationalReportPeriod(start=start, end=end)


def _status_expr():
    return func.lower(func.coalesce(Request.status, ""))


def _open_filter():
    return or_(Request.status.is_(None), ~_status_expr().in_(tuple(CLOSED_STATUSES)))


def _resolved_filter():
    return and_(
        Request.completed_at.isnot(None),
        or_(Request.status.is_(None), _status_expr().in_(tuple(RESOLVED_STATUSES))),
    )


def _base_query(structure_id: int | None = None):
    query = Request.query.filter(Request.deleted_at.is_(None))

    if hasattr(Request, "is_archived"):
        query = query.filter(Request.is_archived.is_(False))

    if structure_id is not None and hasattr(Request, "structure_id"):
        query = query.filter(Request.structure_id == int(structure_id))

    return query


def _count(query) -> int:
    return int(query.count() or 0)


def _duration_hours(start: datetime | None, end: datetime | None) -> float | None:
    start = _normalize_dt(start)
    end = _normalize_dt(end)

    if start is None or end is None or end < start:
        return None

    seconds = (end - start).total_seconds()

    # Ignore impossible legacy/demo values. Reporting should be conservative:
    # better no average than a misleading institutional KPI.
    if seconds < 0 or seconds > 366 * 24 * 3600:
        return None

    return seconds / 3600.0


def _avg_duration_hours(rows, start_attr: str, end_attr: str) -> float:
    values = []
    for row in rows:
        value = _duration_hours(
            getattr(row, start_attr, None),
            getattr(row, end_attr, None),
        )
        if value is not None:
            values.append(value)

    if not values:
        return 0.0

    return round(sum(values) / len(values), 2)



def _build_sparkline_points(values, width=220, height=52):
    if not values:
        return ""

    max_value = max(values) or 1
    step_x = width / max(len(values) - 1, 1)

    points = []

    for idx, value in enumerate(values):
        x = round(idx * step_x, 2)
        y = round(height - ((value / max_value) * height), 2)
        points.append(f"{x},{y}")

    return " ".join(points)
def _rows_by_label(rows, label_name: str, count_name: str = "count") -> list[dict]:
    return [
        {
            label_name: label or "unknown",
            count_name: int(count or 0),
        }
        for label, count in rows
    ]


def _trend_semantic(direction: str, positive_when: str = "up") -> str:
    if direction == "stable":
        return "neutral"

    if direction == positive_when:
        return "positive"

    return "negative"


def _build_trend_metric(current_value: int | float, previous_value: int | float) -> dict:
    current = float(current_value or 0)
    previous = float(previous_value or 0)

    if previous == 0:
        if current == 0:
            return {
                "current": current_value,
                "previous": previous_value,
                "delta_percent": 0.0,
                "direction": "stable",
                "label": "Stable",
            }
        return {
            "current": current_value,
            "previous": previous_value,
            "delta_percent": 100.0,
            "direction": "up",
            "label": "+100%",
        }

    delta = ((current - previous) / previous) * 100
    rounded = round(delta, 1)

    if rounded > 0:
        direction = "up"
        label = f"+{rounded}%"
    elif rounded < 0:
        direction = "down"
        label = f"{rounded}%"
    else:
        direction = "stable"
        label = "Stable"

    return {
        "current": current_value,
        "previous": previous_value,
        "delta_percent": rounded,
        "direction": direction,
        "label": label,
    }


def _build_operational_recommendations(metrics):
    recommendations = []

    open_requests = int(metrics.get("open_requests", 0) or 0)
    unassigned = int(metrics.get("unassigned_requests", 0) or 0)
    stale = int(metrics.get("stale_requests", 0) or 0)
    avg_resolution = float(metrics.get("avg_resolution_hours", 0.0) or 0.0)
    assignment_rate = float(metrics.get("assignment_rate", 0.0) or 0.0)

    if unassigned > 0:
        recommendations.append({
            "priority": "Haute",
            "title": "Réassigner les demandes sans responsable",
            "description": (
                f"{unassigned} situation(s) restent sans responsable identifié. "
                "Une attribution rapide réduit le risque de perte de suivi."
            ),
        })

    if stale > 0:
        recommendations.append({
            "priority": "Haute" if stale >= 5 else "Normale",
            "title": "Relancer les situations sans activité récente",
            "description": (
                f"{stale} situation(s) nécessitent une relance opérationnelle. "
                "Prioriser les dossiers ouverts depuis plus de 72h."
            ),
        })

    if avg_resolution >= 96:
        recommendations.append({
            "priority": "Moyenne",
            "title": "Analyser les délais de résolution",
            "description": (
                f"Le délai moyen de résolution atteint {avg_resolution:.1f}h. "
                "Identifier les catégories ou statuts qui ralentissent le traitement."
            ),
        })

    if assignment_rate < 70 and open_requests > 0:
        recommendations.append({
            "priority": "Moyenne",
            "title": "Renforcer le processus d’assignation",
            "description": (
                f"Le taux d’assignation est de {assignment_rate:.1f}%. "
                "Vérifier les règles d’orientation et la disponibilité des équipes."
            ),
        })

    if not recommendations:
        recommendations.append({
            "priority": "Normale",
            "title": "Maintenir le rythme de suivi",
            "description": (
                "Les indicateurs restent maîtrisés. Continuer le suivi régulier "
                "et conserver la traçabilité des actions."
            ),
        })

    return recommendations[:4]


def _compute_operational_severity(metrics):
    stale = int(metrics.get("stale_requests", 0) or 0)
    unassigned = int(metrics.get("unassigned_requests", 0) or 0)
    avg_resolution = float(metrics.get("avg_resolution_hours", 0.0) or 0.0)

    if stale >= 15 or avg_resolution >= 168:
        return {
            "level": "critical",
            "label": "Critique",
            "message": "Des situations nécessitent une intervention immédiate.",
        }

    if stale >= 5 or unassigned >= 5 or avg_resolution >= 72:
        return {
            "level": "warning",
            "label": "Attention requise",
            "message": "Une tension opérationnelle est détectée.",
        }

    return {
        "level": "stable",
        "label": "Stable",
        "message": "Les indicateurs opérationnels restent maîtrisés.",
    }


def _build_executive_summary(metrics):
    open_requests = int(metrics.get("open_requests", 0) or 0)
    unassigned = int(metrics.get("unassigned_requests", 0) or 0)
    stale = int(metrics.get("stale_requests", 0) or 0)

    avg_resolution = float(metrics.get("avg_resolution_hours", 0.0) or 0.0)
    assignment_rate = float(metrics.get("assignment_rate", 0.0) or 0.0)

    activity_label = (
        "activité soutenue"
        if open_requests >= 20
        else "activité modérée"
        if open_requests >= 10
        else "activité limitée"
    )

    resolution_label = (
        "des délais de résolution élevés"
        if avg_resolution >= 96
        else "des délais de résolution maîtrisés"
    )

    assignment_label = (
        "Le taux d’assignation reste solide."
        if assignment_rate >= 70
        else "Le taux d’assignation nécessite une attention opérationnelle."
    )

    return (
        f"Le pilotage montre une {activity_label} avec "
        f"{open_requests} situations ouvertes, dont "
        f"{unassigned} non assignées. "
        f"La période présente {resolution_label} "
        f"(moyenne: {avg_resolution:.1f}h). "
        f"{stale} situations nécessitent une relance. "
        f"{assignment_label}"
    )


def build_operational_report(
    *,
    structure_id: int | None = None,
    days: int = 7,
    now: datetime | None = None,
) -> dict:
    """
    Build a tenant-safe operational report payload.

    This service deliberately returns data only. Rendering, routes, PDF and CSV
    exports belong to separate layers.
    """
    period = _period_for_days(days, now=now)
    base = _base_query(structure_id=structure_id)

    period_base = base.filter(Request.created_at >= period.start, Request.created_at <= period.end)
    open_base = base.filter(_open_filter())
    resolved_base = base.filter(_resolved_filter())

    stale_threshold = period.end - timedelta(hours=72)

    new_count = _count(period_base)
    resolved_count = _count(
        resolved_base.filter(Request.completed_at >= period.start, Request.completed_at <= period.end)
    )
    open_count = _count(open_base)
    stale_count = _count(
        open_base.filter(Request.created_at.isnot(None)).filter(Request.created_at < stale_threshold)
    )

    unassigned_count = _count(
        open_base.filter(
            or_(
                Request.owner_id.is_(None),
                Request.owned_at.is_(None),
            )
        )
    )

    by_category_rows = (
        period_base.with_entities(Request.category, func.count(Request.id))
        .group_by(Request.category)
        .order_by(func.count(Request.id).desc())
        .limit(10)
        .all()
    )

    by_status_rows = (
        base.with_entities(func.coalesce(Request.status, "unknown"), func.count(Request.id))
        .group_by(func.coalesce(Request.status, "unknown"))
        .order_by(func.count(Request.id).desc())
        .all()
    )

    assignment_rows = (
        base.filter(Request.owned_at.isnot(None))
        .filter(Request.created_at.isnot(None))
        .all()
    )
    resolved_rows = (
        resolved_base.filter(Request.completed_at.isnot(None))
        .filter(Request.created_at.isnot(None))
        .all()
    )

    avg_assignment_hours = _avg_duration_hours(
        assignment_rows,
        "created_at",
        "owned_at",
    )
    avg_resolution_hours = _avg_duration_hours(
        resolved_rows,
        "created_at",
        "completed_at",
    )

    assignment_rate = 0.0
    if open_count > 0:
        assignment_rate = round(((open_count - unassigned_count) / open_count) * 100, 1)

    resolved_under_24h_count = 0
    for row in resolved_rows:
        duration = _duration_hours(
            getattr(row, "created_at", None),
            getattr(row, "completed_at", None),
        )
        if duration is not None and duration <= 24:
            resolved_under_24h_count += 1

    resolved_under_24h_rate = 0.0
    if resolved_count > 0:
        resolved_under_24h_rate = round((resolved_under_24h_count / resolved_count) * 100, 1)

    previous_start = period.start - timedelta(days=days)
    previous_end = period.start

    previous_new_count = _count(
        base.filter(Request.created_at >= previous_start, Request.created_at < previous_end)
    )
    previous_resolved_count = _count(
        resolved_base.filter(
            Request.completed_at >= previous_start,
            Request.completed_at < previous_end,
        )
    )

    trends = {
        "new_requests": {
            **_build_trend_metric(new_count, previous_new_count),
            "semantic": _trend_semantic(
                _build_trend_metric(new_count, previous_new_count)["direction"],
                "down"
            ),
        },
        "resolved_requests": {
            **_build_trend_metric(resolved_count, previous_resolved_count),
            "semantic": _trend_semantic(
                _build_trend_metric(resolved_count, previous_resolved_count)["direction"],
                "up"
            ),
        },
    }

    timeline_map = OrderedDict()
    for offset in range(period.days if hasattr(period, "days") else days):
        current_day = (period.end - timedelta(days=(days - offset - 1))).date()
        timeline_map[str(current_day)] = {
            "created": 0,
            "closed": 0,
        }

    created_timeline_rows = (
        period_base.with_entities(func.date(Request.created_at), func.count(Request.id))
        .group_by(func.date(Request.created_at))
        .all()
    )
    for row_date, row_count in created_timeline_rows:
        key = str(row_date)
        if key in timeline_map:
            timeline_map[key]["created"] = int(row_count or 0)

    closed_timeline_rows = (
        resolved_base.with_entities(func.date(Request.completed_at), func.count(Request.id))
        .filter(Request.completed_at >= period.start, Request.completed_at <= period.end)
        .group_by(func.date(Request.completed_at))
        .all()
    )
    for row_date, row_count in closed_timeline_rows:
        key = str(row_date)
        if key in timeline_map:
            timeline_map[key]["closed"] = int(row_count or 0)

    timeline = [
        {
            "date": key,
            "created": values["created"],
            "closed": values["closed"],
        }
        for key, values in timeline_map.items()
    ]

    report_items = [
        {
            "id": row.id,
            "title": getattr(row, "title", None) or f"Demande #{row.id}",
            "city": getattr(row, "city", None) or "",
            "status": getattr(row, "status", None) or "",
            "priority": getattr(row, "priority", None) or "",
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else "",
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
            "owner_id": getattr(row, "owner_id", None),
        }
        for row in period_base.order_by(Request.created_at.desc()).limit(200).all()
    ]
    timeline_created_values = [
        item["created"]
        for item in timeline
    ]

    timeline_closed_values = [
        item["closed"]
        for item in timeline
    ]

    sla_alerts = build_sla_alerts(
        structure_id=structure_id,
        now=now,
    )

    insight_metrics = {
        "open_requests": open_count,
        "unassigned_requests": unassigned_count,
        "stale_requests": stale_count,
        "avg_resolution_hours": avg_resolution_hours,
        "assignment_rate": assignment_rate,
    }
    executive_summary = _build_executive_summary(insight_metrics)
    operational_severity = _compute_operational_severity(insight_metrics)
    recommendations = _build_operational_recommendations(insight_metrics)

    structure = None
    if structure_id is not None:
        structure = db.session.get(Structure, int(structure_id))

    return {
        "generated_at": period.end.isoformat() + "Z",
        "period": {
            "days": max(1, min(int(days or 7), 366)),
            "start": period.start.isoformat() + "Z",
            "end": period.end.isoformat() + "Z",
        },
        "scope": {
            "structure_id": structure_id,
            "structure_name": getattr(structure, "name", None) if structure else None,
        },
        "requests": {
            "new": new_count,
            "resolved": resolved_count,
            "open": open_count,
            "stale": stale_count,
            "unassigned": unassigned_count,
        },
        "sla": {
            "avg_assignment_hours": avg_assignment_hours,
            "avg_resolution_hours": avg_resolution_hours,
            "assignment_rate": assignment_rate,
            "resolved_under_24h_rate": resolved_under_24h_rate,
        },
        "breakdowns": {
            "by_category": _rows_by_label(by_category_rows, "category"),
            "by_status": _rows_by_label(by_status_rows, "status"),
        },
        "timeline": timeline,
        "items": report_items,
        "timeline_charts": {
            "created": _build_sparkline_points(timeline_created_values),
            "closed": _build_sparkline_points(timeline_closed_values),
        },
        "executive_summary": executive_summary,
        "operational_severity": operational_severity,
        "recommendations": recommendations,
        "sla_alerts": sla_alerts,
        "trends": trends,
        "definition": {
            "scope": "structure-scoped when structure_id is provided; excludes deleted and archived requests",
            "open": "status is not in canonical closed/resolved/cancelled/archived states",
            "resolved": "completed_at is present and status is done/completed/resolved/closed",
            "stale": "open request created more than 72 hours before report generation",
        },
    }
