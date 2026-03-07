from __future__ import annotations

import json


def _signals_set(value) -> set[str]:
    if not value:
        return set()
    if isinstance(value, list):
        return {str(x).strip().lower() for x in value if str(x).strip()}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return set()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return {str(x).strip().lower() for x in parsed if str(x).strip()}
        except Exception:
            pass
        return {part.strip().lower() for part in raw.split(",") if part.strip()}
    return set()


def compute_recommendation(request_obj) -> dict:
    risk_level = (getattr(request_obj, "risk_level", "") or "").strip().lower()
    signals = _signals_set(getattr(request_obj, "risk_signals", None))

    if "violence" in signals:
        return {
            "recommended_action": "protection_escalation",
            "recommended_pathway": "protection",
            "recommended_priority_window": "today",
            "explanation": "Recommendation triggered by: violence risk signal.",
        }

    if risk_level == "critical" and "no_owner" in signals:
        return {
            "recommended_action": "assign_immediately",
            "recommended_pathway": "social_coordination",
            "recommended_priority_window": "today",
            "explanation": "Recommendation triggered by: critical risk + no owner.",
        }

    if "not_seen_72h" in signals:
        return {
            "recommended_action": "manager_review_today",
            "recommended_pathway": "social_coordination",
            "recommended_priority_window": "today",
            "explanation": "Recommendation triggered by: no action seen in the last 72h.",
        }

    if "logement" in signals:
        return {
            "recommended_action": "route_to_housing_partner",
            "recommended_pathway": "housing_support",
            "recommended_priority_window": "24h",
            "explanation": "Signal detected: housing support required.",
        }

    if "alimentation" in signals:
        return {
            "recommended_action": "route_to_food_support",
            "recommended_pathway": "food_support",
            "recommended_priority_window": "48h",
            "explanation": "Signal detected: food support required.",
        }

    if "sante" in signals:
        return {
            "recommended_action": "route_to_health_support",
            "recommended_pathway": "health_support",
            "recommended_priority_window": "24h",
            "explanation": "Signal detected: health support required.",
        }

    return {
        "recommended_action": "routine_queue",
        "recommended_pathway": "general_support",
        "recommended_priority_window": "this_week",
        "explanation": "No high-priority operational trigger detected; keep in routine queue.",
    }
