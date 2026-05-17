from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.models import Request

def _normalize_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value



def build_sla_alerts(
    *,
    structure_id: int | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(UTC)

    query = Request.query

    if structure_id is not None and hasattr(Request, "structure_id"):
        query = query.filter(Request.structure_id == int(structure_id))

    requests = query.all()

    alerts = []

    unassigned_48h = []
    stale_72h = []
    urgent_unassigned = []

    for item in requests:
        created_at = _normalize_datetime(
            getattr(item, "created_at", None)
        )
        updated_at = _normalize_datetime(
            getattr(item, "updated_at", None)
        )
        assigned = bool(getattr(item, "owner_id", None))
        priority = (getattr(item, "priority", None) or "").lower()
        status = (getattr(item, "status", None) or "").lower()

        if status in {"resolved", "closed", "done"}:
            continue

        if (
            not assigned
            and created_at
            and created_at <= now - timedelta(hours=48)
        ):
            unassigned_48h.append(item)

        last_activity = updated_at or created_at

        if (
            last_activity
            and last_activity <= now - timedelta(hours=72)
        ):
            stale_72h.append(item)

        if (
            priority in {"urgent", "critical", "high"}
            and not assigned
        ):
            urgent_unassigned.append(item)

    if unassigned_48h:
        alerts.append({
            "severity": "high",
            "code": "unassigned_48h",
            "title": "Demandes non assignées depuis plus de 48h",
            "count": len(unassigned_48h),
            "action": "Répartir rapidement les demandes sans responsable.",
        })

    if stale_72h:
        alerts.append({
            "severity": "medium",
            "code": "stale_72h",
            "title": "Situations sans activité récente",
            "count": len(stale_72h),
            "action": "Vérifier les situations sans suivi récent.",
        })

    if urgent_unassigned:
        alerts.append({
            "severity": "critical",
            "code": "urgent_unassigned",
            "title": "Situations urgentes sans responsable",
            "count": len(urgent_unassigned),
            "action": "Assigner immédiatement un intervenant.",
        })

    severity_rank = {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }

    highest = "low"

    for alert in alerts:
        if severity_rank[alert["severity"]] > severity_rank[highest]:
            highest = alert["severity"]

    return {
        "generated_at": now.isoformat(),
        "severity": highest,
        "alerts": alerts,
        "metrics": {
            "unassigned_48h": len(unassigned_48h),
            "stale_72h": len(stale_72h),
            "urgent_unassigned": len(urgent_unassigned),
        },
    }
