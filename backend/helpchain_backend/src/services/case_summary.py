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


def _context_sentence(req_obj, signals: set[str]) -> str:
    title = (getattr(req_obj, "title", "") or "").strip().lower()
    description = (getattr(req_obj, "description", "") or "").strip().lower()
    corpus = f"{title} {description}"

    if "logement" in signals or any(
        k in corpus for k in ("logement", "hébergement", "hebergement", "expulsion")
    ):
        return "Situation liée au logement."
    if "alimentation" in signals or any(
        k in corpus for k in ("alimentation", "alimentaire", "repas")
    ):
        return "Situation liée à l’accès à l’aide alimentaire."
    if "sante" in signals or any(
        k in corpus for k in ("santé", "sante", "soin", "médical", "medical")
    ):
        return "Situation liée à un besoin d’accompagnement en santé."
    if "violence" in signals:
        return "Situation nécessitant une vigilance renforcée sur la sécurité."
    return "Situation nécessitant un suivi social."


def _issue_sentence(req_obj, signals: set[str]) -> str:
    risk_level = (getattr(req_obj, "risk_level", "") or "").strip().lower()
    has_owner = bool(getattr(req_obj, "owner_id", None))

    if risk_level == "critical" and not has_owner:
        return "Aucun responsable n’est actuellement assigné."
    if "not_seen_72h" in signals:
        return "Aucune action récente n’a été enregistrée depuis plus de 72 heures."
    if risk_level == "attention":
        return "Le niveau de risque nécessite un suivi rapproché."
    if risk_level == "critical":
        return "Le niveau de risque critique impose un suivi opérationnel immédiat."
    return "La situation reste active et demande une coordination régulière."


def _action_sentence(recommendation: dict | None) -> str:
    rec = recommendation or {}
    action = (rec.get("recommended_action") or "").strip().lower()
    mapping = {
        "assign_immediately": "Une affectation rapide d’un responsable territorial est recommandée.",
        "manager_review_today": "Une revue managériale est recommandée aujourd’hui.",
        "route_to_housing_partner": "Une orientation vers un partenaire logement est recommandée.",
        "route_to_food_support": "Une orientation vers un dispositif d’aide alimentaire est recommandée.",
        "route_to_health_support": "Une orientation vers un appui santé est recommandée.",
        "protection_escalation": "Une escalade de protection doit être engagée sans délai.",
        "routine_queue": "Un suivi courant structuré est recommandé.",
    }
    return mapping.get(action, "Un suivi opérationnel adapté est recommandé.")


def build_case_summary(request_obj, recommendation: dict | None) -> str:
    signals = _signals_set(getattr(request_obj, "risk_signals", None))
    parts = [
        _context_sentence(request_obj, signals),
        _issue_sentence(request_obj, signals),
        _action_sentence(recommendation),
    ]
    return " ".join(parts)


def build_case_summary_snippet(request_obj, recommendation: dict | None, max_len: int = 100) -> str:
    signals = _signals_set(getattr(request_obj, "risk_signals", None))
    if "logement" in signals:
        context = "Logement"
    elif "sante" in signals:
        context = "Santé"
    elif "alimentation" in signals:
        context = "Aide alimentaire"
    elif "not_seen_72h" in signals:
        context = "Absence de suivi"
    else:
        context = "Suivi social"

    issue = _issue_sentence(request_obj, signals).replace(".", "")
    snippet = f"{context} + {issue.lower()}."
    if len(snippet) <= max_len:
        return snippet
    if max_len <= 1:
        return snippet[:max_len]
    return snippet[: max_len - 1].rstrip() + "…"
