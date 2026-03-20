from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, Case, CaseEvent, NotificationJob

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _case_age_hours(case: Case) -> float:
    created_at = _ensure_utc(getattr(case, "created_at", None))
    if not created_at:
        return 0.0
    now = datetime.now(UTC)
    return max((now - created_at).total_seconds() / 3600.0, 0.0)


def _has_recent_event(case_id: int, event_type: str, within_hours: int) -> bool:
    cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
    return (
        db.session.query(CaseEvent.id)
        .filter(
            CaseEvent.case_id == case_id,
            CaseEvent.event_type == event_type,
            CaseEvent.created_at >= cutoff,
        )
        .first()
        is not None
    )


def _add_case_event(case: Case, event_type: str, message: str) -> None:
    db.session.add(
        CaseEvent(
            case_id=case.id,
            actor_user_id=None,
            event_type=event_type,
            message=message,
            visibility="internal",
        )
    )


def _enqueue_notifications(case: Case) -> None:
    if not case.structure_id:
        return
    admins = (
        AdminUser.query.filter(AdminUser.structure_id == case.structure_id)
        .filter(AdminUser.is_active.is_(True))
        .filter(AdminUser.email.isnot(None))
        .all()
    )
    payload = json.dumps(
        {"case_id": case.id, "risk_score": int(case.risk_score or 0)}
    )
    for admin in admins:
        email = (admin.email or "").strip()
        if not email:
            continue
        db.session.add(
            NotificationJob(
                channel="email",
                event_type="critical_case_alert",
                recipient=email,
                payload_json=payload,
                status="pending",
                structure_id=case.structure_id,
            )
        )


def evaluate_case_alerts(case: Case) -> None:
    if not case or not case.id:
        return

    score = int(case.risk_score or 0)
    status = (getattr(case, "status", "") or "").strip().lower()
    is_open = status not in {"closed", "cancelled"}
    age_hours = _case_age_hours(case)

    # SLA breach alerts
    if is_open and age_hours >= 72:
        if not _has_recent_event(case.id, "sla_escalation", 6):
            _add_case_event(case, "sla_escalation", "Case open beyond 72 hours")
    elif is_open and age_hours >= 48:
        if not _has_recent_event(case.id, "sla_warning", 6):
            _add_case_event(case, "sla_warning", "Case open beyond 48 hours")

    # Critical alerts (with spam guard)
    if score >= 90:
        if not _has_recent_event(case.id, "critical_alert", 6):
            _add_case_event(case, "critical_alert", "Critical risk level detected")
            if score >= 95:
                _add_case_event(case, "emergency_case", "Emergency risk level detected")
            _enqueue_notifications(case)
            logger.info(
                "Risk alert generated for case %s (score=%s)",
                case.id,
                score,
            )


def get_active_alerts(structure_id: int):
    if not structure_id:
        return []
    cutoff = datetime.now(UTC) - timedelta(hours=72)
    return (
        Case.query.filter(Case.structure_id == structure_id)
        .filter(
            (Case.risk_score >= 90)
            | (
                (Case.created_at <= cutoff)
                & (Case.status.isnot(None))
                & (Case.status != "closed")
            )
        )
        .order_by(Case.risk_score.desc())
        .all()
    )
