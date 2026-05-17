from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_

from backend.extensions import db
from backend.models import Request, Structure


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


def _seconds_diff(end_col, start_col):
    dialect = (db.session.bind.dialect.name if db.session.bind is not None else "").lower()

    if dialect == "sqlite":
        return func.strftime("%s", end_col) - func.strftime("%s", start_col)

    if dialect == "postgresql":
        return func.extract("epoch", end_col - start_col)

    return func.extract("epoch", end_col - start_col)


def _rows_by_label(rows, label_name: str, count_name: str = "count") -> list[dict]:
    return [
        {
            label_name: label or "unknown",
            count_name: int(count or 0),
        }
        for label, count in rows
    ]


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

    avg_assign_sec = (
        base.with_entities(func.avg(_seconds_diff(Request.owned_at, Request.created_at)))
        .filter(Request.owned_at.isnot(None))
        .filter(Request.created_at.isnot(None))
        .filter(Request.owned_at >= Request.created_at)
        .scalar()
    )

    avg_resolve_sec = (
        resolved_base.with_entities(func.avg(_seconds_diff(Request.completed_at, Request.created_at)))
        .filter(Request.completed_at.isnot(None))
        .filter(Request.created_at.isnot(None))
        .filter(Request.completed_at >= Request.created_at)
        .scalar()
    )

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
            "avg_assignment_hours": round(float(avg_assign_sec or 0) / 3600.0, 2),
            "avg_resolution_hours": round(float(avg_resolve_sec or 0) / 3600.0, 2),
        },
        "breakdowns": {
            "by_category": _rows_by_label(by_category_rows, "category"),
            "by_status": _rows_by_label(by_status_rows, "status"),
        },
        "definition": {
            "scope": "structure-scoped when structure_id is provided; excludes deleted and archived requests",
            "open": "status is not in canonical closed/resolved/cancelled/archived states",
            "resolved": "completed_at is present and status is done/completed/resolved/closed",
            "stale": "open request created more than 72 hours before report generation",
        },
    }
