from __future__ import annotations

from typing import Any

from ..constants.categories import normalize_request_category


def compute_next_best_action(case_row, request_obj=None) -> dict[str, Any]:
    """Return a simple, explainable next-best-action recommendation for operators."""
    req = request_obj or getattr(case_row, "request", None)
    category = normalize_request_category(getattr(req, "category", None))
    priority = (getattr(case_row, "priority", None) or getattr(req, "priority", "") or "").strip().lower()
    risk_score = int(getattr(case_row, "risk_score", 0) or getattr(req, "risk_score", 0) or 0)
    has_owner = bool(getattr(case_row, "owner_user_id", None))

    reasons: list[str] = []

    if priority == "critical" or risk_score >= 85:
        reasons.append("priorité critique")
        if risk_score >= 85:
            reasons.append("risque élevé")
        return {"next_action": "escalate_supervisor", "reason": reasons}

    if not has_owner:
        reasons.append("non assigné")
        return {"next_action": "assign_internal", "reason": reasons}

    if category == "housing":
        reasons.append("catégorie logement")
        return {"next_action": "contact_housing_partner", "reason": reasons}

    if category == "violence":
        reasons.append("catégorie protection/violence")
        return {"next_action": "contact_legal_partner", "reason": reasons}

    if category in {"health", "isolation"}:
        reasons.append("catégorie santé/isolement")
        return {"next_action": "contact_psych_partner", "reason": reasons}

    return {"next_action": "review_manually", "reason": ["revue nécessaire"]}
