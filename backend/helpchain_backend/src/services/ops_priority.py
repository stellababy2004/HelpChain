from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


def _as_aware_utc(dt_val: datetime | None) -> datetime | None:
    if not dt_val:
        return None
    if dt_val.tzinfo is None:
        return dt_val.replace(tzinfo=timezone.utc)
    return dt_val.astimezone(timezone.utc)


def _text_blob(*parts: Optional[str]) -> str:
    return " ".join(p for p in (part or "" for part in parts) if p).strip().lower()


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def compute_ops_priority(
    *,
    case_row=None,
    request_row=None,
    notification_failed: bool = False,
    activity_ref=None,
    now: datetime | None = None,
) -> dict:
    now_utc = now or datetime.now(timezone.utc)

    priority_val = ""
    risk_score = 0
    owner_id = None
    activity_ref = activity_ref
    title = ""
    description = ""
    message = ""

    if case_row is not None:
        priority_val = (getattr(case_row, "priority", "") or "").strip().lower()
        risk_score = int(getattr(case_row, "risk_score", 0) or 0)
        owner_id = getattr(case_row, "owner_user_id", None)
        activity_ref = (
            getattr(case_row, "last_activity_at", None)
            or getattr(case_row, "updated_at", None)
            or getattr(case_row, "created_at", None)
        )

    if request_row is not None:
        if not priority_val:
            priority_val = (getattr(request_row, "priority", "") or "").strip().lower()
        if not risk_score:
            risk_score = int(getattr(request_row, "risk_score", 0) or 0)
        if owner_id is None:
            owner_id = getattr(request_row, "owner_id", None)
        if activity_ref is None:
            activity_ref = getattr(request_row, "updated_at", None) or getattr(
                request_row, "created_at", None
            )
        title = getattr(request_row, "title", "") or ""
        description = getattr(request_row, "description", "") or ""
        message = getattr(request_row, "message", "") or ""

    score = 0
    reasons: list[str] = []

    if priority_val == "critical":
        score += 45
        reasons.append("PrioritÃ© critique")
    elif priority_val == "high":
        score += 30
        reasons.append("PrioritÃ© Ã©levÃ©e")

    if risk_score >= 85:
        score += 35
        if "Risque critique" not in reasons:
            reasons.append("Risque critique")
    elif risk_score >= 60:
        score += 20
        if "Risque Ã©levÃ©" not in reasons:
            reasons.append("Risque Ã©levÃ©")

    if owner_id is None:
        score += 20
        reasons.append("Sans responsable")

    activity_aware = _as_aware_utc(activity_ref)
    if activity_aware:
        inactive_for = now_utc - activity_aware
        if inactive_for >= timedelta(days=7):
            score += 30
            reasons.append("Sans action 7j")
        elif inactive_for >= timedelta(hours=72):
            score += 20
            reasons.append("Sans action 72h")

    text = _text_blob(title, description, message)
    essential_keywords = (
        "sans nourriture",
        "faim",
        "pas Ã  manger",
        "pas a manger",
        "sans manger",
        "sans logement",
        "sans abri",
        "Ã  la rue",
        "a la rue",
        "dehors ce soir",
        "sans chauffage",
        "pas de chauffage",
        "sans Ã©lectricitÃ©",
        "sans electricite",
        "sans eau",
        "pas d'eau",
        "plus de mÃ©dicaments",
        "plus de medicaments",
        "sans mÃ©dicaments",
        "sans medicaments",
    )
    if text and _has_any(text, essential_keywords):
        score += 20
        reasons.append("Besoin essentiel dÃ©tectÃ©")

    vulnerability_keywords = (
        "personne Ã¢gÃ©e",
        "personne agee",
        "Ã¢gÃ©e",
        "agee",
        "senior",
        "handicap",
        "handicapÃ©",
        "handicape",
        "enfant",
        "bÃ©bÃ©",
        "bebe",
        "mineur",
        "grossesse",
        "enceinte",
    )
    if text and _has_any(text, vulnerability_keywords):
        score += 10
        reasons.append("VulnÃ©rabilitÃ© probable")

    if notification_failed:
        score += 15
        reasons.append("Notification Ã©chouÃ©e")

    level = "normal"
    if score >= 80:
        level = "critique"
    elif score >= 50:
        level = "Ã©levÃ©"

    return {
        "ops_priority_score": score,
        "ops_priority_level": level,
        "ops_priority_reasons": reasons,
    }


