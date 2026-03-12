from __future__ import annotations

from datetime import UTC, datetime


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _case_has_owner(case_row) -> bool:
    if getattr(case_row, "owner_user_id", None):
        return True
    participants = getattr(case_row, "participants", None) or []
    return any(
        ((getattr(participant, "role", None) or "").strip().lower() == "owner")
        and bool(getattr(participant, "user_id", None) or getattr(participant, "external_name", None))
        for participant in participants
    )


def _case_has_professional(case_row) -> bool:
    if getattr(case_row, "assigned_professional_lead_id", None):
        return True
    participants = getattr(case_row, "participants", None) or []
    return any(
        bool(getattr(participant, "professional_lead_id", None))
        and (
            (getattr(participant, "role", None) or "").strip().lower() == "primary_professional"
            or (getattr(participant, "participant_type", None) or "").strip().lower() == "professional_lead"
        )
        for participant in participants
    )


def build_case_assistant_recommendation(case_row, request_obj, triage: dict, suggested_professionals: list[dict] | None = None) -> dict:
    suggested_professionals = suggested_professionals or []
    risk_label = (triage.get("risk_label") or "").upper()
    derived_priority = (triage.get("derived_priority") or "").lower()
    category_code = (
        getattr(request_obj, "category", None)
        or triage.get("suggested_category_code")
        or ""
    ).strip().lower()
    matched_labels = [str(item.get("label") or "") for item in (triage.get("matched_rules") or [])]

    reason_tags: list[str] = []
    action_code = "standard_follow_up"
    action_label = "Poursuivre le traitement standard"
    urgency = "monitor"
    operator_summary = "Situation sans signal critique immédiat. Maintenir un suivi opérationnel normal."

    last_activity = _coerce_utc(
        getattr(case_row, "last_activity_at", None)
        or getattr(case_row, "updated_at", None)
        or getattr(case_row, "created_at", None)
    )
    stale_hours = None
    if last_activity:
        stale_hours = max(0, int((_now_utc() - last_activity).total_seconds() // 3600))

    top_match = suggested_professionals[0] if suggested_professionals else None
    has_strong_match = bool(top_match and int(top_match.get("score") or 0) >= 60)
    no_owner = not _case_has_owner(case_row)
    no_professional = not _case_has_professional(case_row)

    if risk_label == "CRITICAL" and no_owner:
        action_code = "assign_owner_immediately"
        action_label = "Assigner un responsable immédiatement"
        urgency = "immediate"
        reason_tags = ["risque critique", "aucun responsable"]
        operator_summary = "Le dossier est critique et aucun opérateur n'est responsable. Affecter un responsable maintenant."
    elif risk_label == "CRITICAL" and no_professional:
        action_code = "assign_professional_immediately"
        action_label = "Assigner un professionnel immédiatement"
        urgency = "immediate"
        reason_tags = ["risque critique", "aucun professionnel"]
        if has_strong_match:
            reason_tags.append("correspondance disponible")
            operator_summary = "Le dossier est critique et un professionnel pertinent est disponible dans les suggestions. Affectation immédiate recommandée."
        else:
            operator_summary = "Le dossier est critique et aucun professionnel n'est encore assigné. Prioriser une orientation immédiate."
    elif derived_priority in {"critical", "high"} and stale_hours is not None and stale_hours >= 72:
        action_code = "relance_immediate"
        action_label = "Relancer le dossier immédiatement"
        urgency = "immediate"
        reason_tags = ["dossier stale", f"sans action {stale_hours}h", f"priorite {derived_priority}"]
        operator_summary = "Le dossier présente un risque élevé et n'a pas reçu d'action récente. Une relance immédiate est recommandée."
    elif category_code in {"violence", "emergency"} and has_strong_match and no_professional:
        action_code = "assign_protection_match"
        action_label = "Assigner le professionnel de protection suggéré"
        urgency = "today"
        reason_tags = ["catégorie sensible", "professionnel compatible", "mise en relation prioritaire"]
        operator_summary = "La situation relève de la protection et une correspondance professionnelle exploitable est disponible. Affectation rapide recommandée."
    elif category_code == "health" and any("medical" in label for label in matched_labels):
        action_code = "orient_health_quickly"
        action_label = "Orienter vers un professionnel de santé rapidement"
        urgency = "today"
        reason_tags = ["santé", "détresse médicale"]
        operator_summary = "Des signaux de santé ont été détectés. Une orientation rapide vers un professionnel de santé est recommandée."
    elif category_code == "admin_help" and risk_label in {"LOW", "NORMAL"}:
        action_code = "standard_admin_processing"
        action_label = "Traiter en file standard"
        urgency = "24h"
        reason_tags = ["aide administrative", "risque limité"]
        operator_summary = "La situation relève d'un traitement administratif standard sans signal de crise immédiate."
    elif no_owner:
        action_code = "assign_owner"
        action_label = "Assigner un responsable"
        urgency = "today"
        reason_tags = ["pilotage", "responsable requis"]
        operator_summary = "Le dossier doit être pris en charge par un opérateur identifié pour avancer."
    elif no_professional and has_strong_match:
        action_code = "review_professional_suggestions"
        action_label = "Examiner et assigner un professionnel suggéré"
        urgency = "24h"
        reason_tags = ["matching disponible", "professionnel non assigné"]
        operator_summary = "Une correspondance professionnelle crédible est disponible et peut accélérer la prise en charge."

    return {
        "action_code": action_code,
        "action_label": action_label,
        "urgency": urgency,
        "reason_tags": reason_tags,
        "operator_summary": operator_summary,
    }
