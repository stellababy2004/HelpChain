from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.extensions import db
from backend.helpchain_backend.src.models import Case, CaseEvent
from backend.models import Assignment


def _as_naive_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


KEYWORDS_VIOLENCE = ("violence", "abuse", "danger", "threat")
KEYWORDS_ELDERLY = ("elderly", "no heating", "cold", "alone")
KEYWORDS_FOOD = ("food", "hunger", "no meal")


def _urgency_score(urgency: str | None) -> int:
    value = (urgency or "").strip().lower()
    if value == "critical":
        return 40
    if value == "high":
        return 25
    if value == "medium":
        return 10
    return 0


def _text_score(text: str) -> int:
    score = 0
    lowered = text.lower()
    if any(k in lowered for k in KEYWORDS_VIOLENCE):
        score += 40
    if any(k in lowered for k in KEYWORDS_ELDERLY):
        score += 25
    if any(k in lowered for k in KEYWORDS_FOOD):
        score += 15
    return score


def _risk_bucket(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def calculate_case_risk(case: Case) -> int:
    if str(getattr(case, "status", "")).lower() == "closed":
        return 0

    total = 0
    req = getattr(case, "request", None)
    urgency = None
    if req is not None:
        urgency = getattr(req, "urgency", None) or getattr(req, "priority", None)
    total += _urgency_score(urgency)

    text_parts = []
    if getattr(case, "description", None):
        text_parts.append(getattr(case, "description"))
    if req is not None and getattr(req, "description", None):
        text_parts.append(getattr(req, "description"))
    total += _text_score(" ".join(text_parts))

    has_assignment = (
        db.session.query(Assignment.id)
        .filter(Assignment.request_id == case.request_id)
        .first()
        is not None
    )
    if not has_assignment:
        total += 10

    created_at = _as_naive_utc(getattr(case, "created_at", None))
    now = datetime.now(UTC).replace(tzinfo=None)
    if created_at:
        age = now - created_at
        if age >= timedelta(hours=72):
            total += 20
        elif age >= timedelta(hours=48):
            total += 10

    return min(int(total), 100)


def update_case_risk(case: Case) -> int:
    score = calculate_case_risk(case)
    case.risk_score = int(score)
    return int(score)


def compute_case_risk(case_id: int) -> dict | None:
    case = db.session.get(Case, int(case_id))
    if not case:
        return None

    score = calculate_case_risk(case)

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
    created_at = _as_naive_utc(getattr(case, "created_at", None))
    now = datetime.now(UTC).replace(tzinfo=None)
    days_open = int(max((now - created_at).days, 0)) if created_at else 0

    return {
        "case_id": case.id,
        "risk_score": int(score),
        "risk_level": _risk_bucket(int(score)),
        "factors": {
            "case_age_days": int(days_open),
            "events_count": int(events_count),
            "no_assignment": bool(not has_assignment),
        },
    }


def get_critical_cases(structure_id: int | None):
    q = db.session.query(Case).filter(Case.risk_score >= 80)
    if structure_id is not None:
        q = q.filter(Case.structure_id == structure_id)
    return q.order_by(Case.risk_score.desc()).all()


def get_risk_metrics(structure_id: int | None) -> dict:
    q = db.session.query(Case)
    if structure_id is not None:
        q = q.filter(Case.structure_id == structure_id)

    cases = q.all()
    metrics = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for c in cases:
        bucket = _risk_bucket(int(getattr(c, "risk_score", 0) or 0))
        if bucket == "critical":
            metrics["critical"] += 1
        elif bucket == "high":
            metrics["high"] += 1
        elif bucket == "medium":
            metrics["medium"] += 1
        else:
            metrics["low"] += 1
    return metrics


def risk_color(score: int) -> str:
    if score >= 80:
        return "red"
    if score >= 60:
        return "orange"
    if score >= 30:
        return "yellow"
    return "green"


def register_request_risk_hooks():
    """
    Placeholder for future risk hooks.
    Keeps app factory import stable.
    """
    return None
