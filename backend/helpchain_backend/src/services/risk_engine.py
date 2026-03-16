from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db
from backend.helpchain_backend.src.models import Case, CaseEvent
from backend.models import Assignment


def _as_naive_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def _risk_level(score: float) -> str:
    if score >= 15:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def compute_case_risk(case_id: int) -> dict | None:
    case = db.session.get(Case, int(case_id))
    if not case:
        return None

    created_at = _as_naive_utc(getattr(case, "created_at", None))
    now = datetime.now(UTC).replace(tzinfo=None)
    days_open = int(max((now - created_at).days, 0)) if created_at else 0

    events_count = (
        db.session.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id)
        .count()
    )

    has_assignment = (
        db.session.query(Assignment.id)
        .filter(Assignment.request_id == case.request_id)
        .first()
        is not None
    )
    no_assignment = not has_assignment

    if str(getattr(case, "status", "")).lower() == "closed":
        score = 0.0
    else:
        score = (days_open * 0.5) + (events_count * 0.3) + (10 if no_assignment else 0)

    return {
        "case_id": case.id,
        "risk_score": float(round(score, 2)),
        "risk_level": _risk_level(score),
        "factors": {
            "case_age_days": int(days_open),
            "events_count": int(events_count),
            "no_assignment": bool(no_assignment),
        },
    }


def register_request_risk_hooks():
    """
    Placeholder for future risk hooks.
    Keeps app factory import stable.
    """
    return None
