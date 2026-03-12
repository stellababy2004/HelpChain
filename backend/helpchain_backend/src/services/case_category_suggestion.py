from __future__ import annotations

from ..constants.categories import request_category_label


SEVERE_SIGNAL_LABELS = {
    "violence",
    "medical_distress",
    "no_housing",
    "no_food",
}

ADMIN_INFO_TOKENS = (
    "administratif",
    "administrative",
    "papier",
    "documents",
    "dossier",
    "formulaire",
    "attestation",
    "caf",
    "rsa",
    "cpam",
    "prefecture",
    "impot",
    "impots",
    "ameli",
)

EMERGENCY_TOKENS = (
    "urgence",
    "danger immediat",
    "danger immédiat",
    "immediat",
    "immédiat",
)


def suggest_case_category(
    *,
    matched_rule_labels: list[str],
    normalized_text: str,
    risk_score: int,
) -> str | None:
    labels = {str(lbl or "").strip().lower() for lbl in matched_rule_labels}
    text = (normalized_text or "").strip().lower()

    severe_matches = labels.intersection(SEVERE_SIGNAL_LABELS)
    emergency_by_mix = len(severe_matches) >= 2 and int(risk_score or 0) >= 85
    emergency_by_text = any(tok in text for tok in EMERGENCY_TOKENS)
    if emergency_by_mix or emergency_by_text:
        return "emergency"

    if "violence" in labels:
        return "violence"
    if "no_food" in labels:
        return "food"
    if "no_housing" in labels:
        return "housing"
    if "medical_distress" in labels:
        return "health"
    if "isolation" in labels or "elderly_in_difficulty" in labels:
        return "isolation"

    if "category:sante" in labels or "category:medical" in labels:
        return "health"
    if "category:hebergement" in labels or "category:logement" in labels:
        return "housing"
    if "category:protection" in labels:
        return "violence"

    has_admin_info_pattern = any(tok in text for tok in ADMIN_INFO_TOKENS)
    has_social_distress_signal = bool(
        labels.intersection(
            {
                "violence",
                "no_food",
                "no_housing",
                "medical_distress",
                "isolation",
                "elderly_in_difficulty",
                "child_involved",
            }
        )
    )
    if has_admin_info_pattern and not has_social_distress_signal:
        return "admin_help"

    return None


def suggested_category_label(code: str | None) -> str | None:
    if not code:
        return None
    return request_category_label(code)

