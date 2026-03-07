from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import event

from ..models import Request

RISK_STANDARD = "standard"
RISK_ATTENTION = "attention"
RISK_CRITICAL = "critical"

_RISK_HOOKS_INSTALLED = False


def _add_signal(signals: list[str], signal: str) -> None:
    if signal and signal not in signals:
        signals.append(signal)


def _contains_any(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    haystack = text.lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def compute_request_risk(request_obj) -> dict:
    """
    Rule-based AI Social Risk Engine v1.
    AI-assisted, not AI-decided.
    """
    score = 0
    signals: list[str] = []

    description = " ".join(
        [
            getattr(request_obj, "title", "") or "",
            getattr(request_obj, "description", "") or "",
            getattr(request_obj, "category", "") or "",
            getattr(request_obj, "subcategory", "") or "",
        ]
    ).strip()

    if _contains_any(
        description,
        ["sante", "santé", "health", "medical", "médical", "traitement", "urgence medicale", "urgence médicale"],
    ):
        score += 25
        _add_signal(signals, "sante")

    if _contains_any(
        description,
        ["violence", "danger", "agression", "abuse", "maltraitance", "unsafe"],
    ):
        score += 35
        _add_signal(signals, "violence")

    if _contains_any(
        description,
        ["logement", "sans abri", "hebergement", "hébergement", "expulsion", "homeless", "shelter"],
    ):
        score += 25
        _add_signal(signals, "logement")

    if _contains_any(
        description,
        ["alimentaire", "nourriture", "faim", "food", "hungry"],
    ):
        score += 20
        _add_signal(signals, "alimentation")

    if _contains_any(
        description,
        ["isole", "isolé", "isolement", "sans reseau", "sans réseau", "alone", "isolated"],
    ):
        score += 20
        _add_signal(signals, "isolement")

    if _contains_any(
        description,
        ["enfant", "children", "famille monoparentale", "single mother", "single parent"],
    ):
        score += 20
        _add_signal(signals, "famille_vulnerable")

    if _contains_any(
        description,
        ["urgent", "urgence", "immediat", "immédiat", "immediate", "asap"],
    ):
        score += 20
        _add_signal(signals, "urgence")

    assigned_volunteer_id = getattr(request_obj, "assigned_volunteer_id", None)
    owner_id = getattr(request_obj, "owner_id", None) or getattr(
        request_obj, "assigned_to_user_id", None
    )
    if not assigned_volunteer_id and not owner_id:
        score += 15
        _add_signal(signals, "no_owner")

    updated_at = getattr(request_obj, "updated_at", None)
    created_at = getattr(request_obj, "created_at", None)
    reference_dt = updated_at or created_at
    if isinstance(reference_dt, datetime):
        now = datetime.now(UTC)
        if reference_dt.tzinfo is None:
            reference_dt = reference_dt.replace(tzinfo=UTC)
        hours_since_update = (now - reference_dt).total_seconds() / 3600
        if hours_since_update >= 72:
            score += 20
            _add_signal(signals, "not_seen_72h")
        elif hours_since_update >= 48:
            score += 15
            _add_signal(signals, "stale_48h")

    status = (getattr(request_obj, "status", "") or "").lower()
    if status in {"new", "pending", "unassigned"}:
        score += 10
        _add_signal(signals, f"status_{status}")

    score = min(score, 100)
    if score >= 70:
        level = RISK_CRITICAL
    elif score >= 40:
        level = RISK_ATTENTION
    else:
        level = RISK_STANDARD

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_signals": signals,
        "risk_last_updated": datetime.now(UTC),
    }


def apply_request_risk(request_obj) -> None:
    result = compute_request_risk(request_obj)
    request_obj.risk_score = result["risk_score"]
    request_obj.risk_level = result["risk_level"]
    request_obj.risk_signals = json.dumps(result["risk_signals"], ensure_ascii=False)
    request_obj.risk_last_updated = result["risk_last_updated"]


def register_request_risk_hooks() -> None:
    global _RISK_HOOKS_INSTALLED
    if _RISK_HOOKS_INSTALLED:
        return

    @event.listens_for(Request, "before_insert")
    def _request_before_insert(mapper, connection, target) -> None:
        apply_request_risk(target)

    @event.listens_for(Request, "before_update")
    def _request_before_update(mapper, connection, target) -> None:
        apply_request_risk(target)

    _RISK_HOOKS_INSTALLED = True
