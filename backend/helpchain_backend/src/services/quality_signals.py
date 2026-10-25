"""Deterministic, read-only operational quality signals.

This module deliberately contains no AI, persistence, network calls, or task
queue integration.  It turns existing request facts into explainable signals.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..statuses import request_terminal_status_read_values
from .request_sla import DEFAULT_ESCALATION_THRESHOLD_HOURS



def compute_quality_signals(
    request_obj,
    *,
    now: datetime | None = None,
    last_activity_at: datetime | None = None,
    overdue: bool = False,
    no_activity_hours: int = DEFAULT_ESCALATION_THRESHOLD_HOURS,
) -> dict[str, object]:
    """Return explainable signals for one active canonical Request.

    ``last_activity_at`` and ``overdue`` are supplied by the caller so the
    service can reuse the project's existing activity and SLA semantics.
    """
    status = (getattr(request_obj, "status", None) or "").strip().lower()
    if (
        getattr(request_obj, "deleted_at", None) is not None
        or bool(getattr(request_obj, "is_archived", False))
        or status in request_terminal_status_read_values()
    ):
        return {"level": "normal", "signals": [], "reasons": []}

    now_value = now or datetime.now(UTC)
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=UTC)
    activity = last_activity_at or getattr(request_obj, "updated_at", None) or getattr(
        request_obj, "created_at", None
    )
    if activity is not None:
        if activity.tzinfo is None:
            activity = activity.replace(tzinfo=UTC)

    signals: list[str] = []
    reasons: list[str] = []

    if not getattr(request_obj, "owner_id", None):
        signals.append("unassigned")
        reasons.append("No operational owner is assigned")

    if activity is not None and now_value - activity >= timedelta(hours=no_activity_hours):
        signals.append("no_recent_activity")
        reasons.append(f"No meaningful activity for at least {no_activity_hours} hours")

    if overdue:
        signals.append("overdue")
        reasons.append("An existing HelpChain SLA/deadline is overdue")

    if "no_recent_activity" in signals and "unassigned" in signals:
        signals.append("possible_followup_break")
        reasons.append("No recent activity and no operational owner")

    if "possible_followup_break" in signals or "overdue" in signals:
        level = "high_attention"
    elif "no_recent_activity" in signals:
        level = "follow_up_needed"
    elif signals:
        level = "attention"
    else:
        level = "normal"

    return {"level": level, "signals": signals, "reasons": reasons}
