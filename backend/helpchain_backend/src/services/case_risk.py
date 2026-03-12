from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from .case_category_suggestion import suggest_case_category, suggested_category_label

@dataclass(frozen=True)
class RuleMatch:
    label: str
    weight: int
    family: str = "general"
    severe: bool = False


SEVERE_RISK_RULES: tuple[tuple[str, tuple[str, ...], int, str], ...] = (
    ("suicide_risk", ("suicide", "suicidaire", "me tuer", "envie de mourir", "fin a mes jours", "mettre fin a mes jours", "je veux mourir", "me faire du mal"), 70, "suicide"),
    ("domestic_violence_immediate_danger", ("violence conjugale", "battue", "frappee", "frappe", "agression", "menace", "danger immediat", "protection immediate", "violent a la maison"), 68, "violence"),
    ("child_in_danger", ("enfant en danger", "mineur en danger", "violence enfant", "maltraitance enfant", "bebe en danger", "nourrisson en danger"), 72, "child"),
    ("elderly_acute_danger", ("personne agee seule", "personne agee sans aide", "chute", "confusion", "personne vulnerable sans aide"), 58, "elderly"),
    ("urgent_medical_distress", ("urgence medicale", "detresse medicale", "douleur intense", "besoin medical urgent", "respire mal", "hemorragie", "crise grave"), 65, "medical"),
    ("urgent_shelter_tonight", ("dehors ce soir", "sans logement ce soir", "hebergement urgent", "a la rue ce soir", "sans abri ce soir"), 58, "housing"),
    ("trapped_without_support", ("enferme", "bloque sans aide", "sans aucun soutien", "besoin de protection immediate", "impossible de sortir"), 56, "protection"),
)

HIGH_RISK_RULES: tuple[tuple[str, tuple[str, ...], int, str], ...] = (
    ("violence", ("violence", "violent", "agression", "menace", "danger"), 38, "violence"),
    ("medical_distress", ("detresse medicale", "detresse", "crise"), 36, "medical"),
    ("child_involved", ("enfant", "mineur", "bebe", "nourrisson"), 30, "child"),
    ("elderly_in_difficulty", ("personne agee", "senior", "dependance", "alzheim"), 24, "elderly"),
    ("no_housing", ("sans abri", "sans logement", "expulsion", "hebergement urgence", "a la rue"), 34, "housing"),
    ("no_food", ("pas de nourriture", "faim", "aide alimentaire", "pas a manger", "sans nourriture"), 28, "food"),
    ("isolation", ("isole", "isolement", "seul", "solitude", "sans aide"), 20, "isolation"),
)

CATEGORY_RULES: tuple[tuple[str, int], ...] = (
    ("sante", 16),
    ("medical", 16),
    ("urgence", 18),
    ("hebergement", 18),
    ("logement", 18),
    ("protection", 18),
)

PRIORITY_RULES: dict[str, int] = {
    "critical": 28,
    "urgent": 24,
    "high": 16,
    "medium": 8,
    "normal": 4,
    "low": 0,
}

EMERGENCY_REASON_LABELS: dict[str, str] = {
    "suicide": "Signaux de detresse suicidaire detectes",
    "violence": "Violence / danger immediat detecte",
    "child": "Enfant potentiellement en danger",
    "elderly": "Personne agee vulnerable en danger aigu",
    "food_housing_vulnerability": "Isolement + absence de nourriture ou d'hebergement + vulnerabilite detectes",
    "medical": "Signaux de detresse medicale urgente detectes",
    "protection": "Protection immediate a evaluer",
}


def _normalize_text(value: str | None) -> str:
    txt = (value or "").strip().lower()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = txt.replace("-", " ").replace("_", " ")
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(_normalize_text(needle) in text for needle in needles)


def _format_emergency_reason(families: list[str]) -> str:
    labels = [EMERGENCY_REASON_LABELS[f] for f in families if f in EMERGENCY_REASON_LABELS]
    if not labels:
        return "Situation critique detectee par analyse de regles"
    if len(labels) == 1:
        return labels[0]
    return " ; ".join(labels[:2])


def priority_from_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "normal"
    return "low"


def risk_label_from_score(score: int) -> str:
    p = priority_from_score(score)
    if p == "critical":
        return "CRITICAL"
    if p == "high":
        return "HIGH"
    if p == "normal":
        return "NORMAL"
    return "LOW"


def score_request_risk(request_obj) -> dict:
    title = _normalize_text(getattr(request_obj, "title", None))
    description = _normalize_text(getattr(request_obj, "description", None))
    message = _normalize_text(getattr(request_obj, "message", None))
    category = _normalize_text(getattr(request_obj, "category", None))
    request_priority = _normalize_text(getattr(request_obj, "priority", None))
    existing_risk_level = _normalize_text(getattr(request_obj, "risk_level", None))
    combined_text = " ".join(part for part in (title, description, message, category) if part).strip()

    matched: list[RuleMatch] = []
    score = 0

    for label, terms, weight, family in SEVERE_RISK_RULES:
        if _contains_any(combined_text, terms):
            matched.append(RuleMatch(label=label, weight=weight, family=family, severe=True))
            score += weight

    for label, terms, weight, family in HIGH_RISK_RULES:
        if _contains_any(combined_text, terms):
            matched.append(RuleMatch(label=label, weight=weight, family=family, severe=False))
            score += weight

    for cat_key, weight in CATEGORY_RULES:
        if cat_key and cat_key in category:
            matched.append(RuleMatch(label=f"category:{cat_key}", weight=weight, family="category"))
            score += weight
            break

    if request_priority in PRIORITY_RULES:
        pr_weight = PRIORITY_RULES[request_priority]
        if pr_weight > 0:
            matched.append(RuleMatch(label=f"request_priority:{request_priority}", weight=pr_weight, family="priority"))
            score += pr_weight

    if existing_risk_level in {"critical", "high", "attention"}:
        lvl_weight = 22 if existing_risk_level == "critical" else 14
        matched.append(RuleMatch(label=f"request_risk_level:{existing_risk_level}", weight=lvl_weight, family="risk_level"))
        score += lvl_weight

    severe_matches = [m for m in matched if m.severe]
    severe_families = list(dict.fromkeys(m.family for m in severe_matches if m.family))
    all_families = {m.family for m in matched if m.family}
    combo_food_housing_vulnerability = (
        ("food" in all_families or "housing" in all_families)
        and ("elderly" in all_families or "child" in all_families or "isolation" in all_families)
    )
    combo_multiple_high_risk = len([m for m in matched if m.weight >= 28]) >= 2

    emergency_detected = bool(
        any(m.weight >= 65 for m in severe_matches)
        or len(severe_matches) >= 2
        or combo_food_housing_vulnerability
        or combo_multiple_high_risk and score >= 70
    )
    if emergency_detected and combo_food_housing_vulnerability and "food_housing_vulnerability" not in severe_families:
        severe_families.append("food_housing_vulnerability")

    score = max(0, min(int(score), 100))
    has_strong_signal = any(m.weight >= 28 for m in matched)
    if emergency_detected:
        score = max(score, 85)

    derived_priority = "critical" if emergency_detected else priority_from_score(score)
    if score < 30 and not has_strong_signal and not emergency_detected:
        derived_priority = "normal"

    matched_rules = [
        {"label": m.label, "weight": m.weight, "family": m.family, "severe": m.severe}
        for m in matched
    ]
    matched_rule_labels = [m["label"] for m in matched_rules]
    suggested_category_code = suggest_case_category(
        matched_rule_labels=matched_rule_labels,
        normalized_text=combined_text,
        risk_score=score,
    )
    suggested_label = suggested_category_label(suggested_category_code)
    risk_label = "CRITICAL" if emergency_detected else risk_label_from_score(score)
    emergency_reason_summary = _format_emergency_reason(severe_families) if emergency_detected else None

    return {
        # Existing keys kept for backward compatibility.
        "score": score,
        "priority": derived_priority,
        "label": risk_label,
        # New explicit keys (v1 suggestion layer).
        "risk_score": score,
        "risk_label": risk_label,
        "derived_priority": derived_priority,
        "matched_rules": matched_rules,
        "suggested_category_code": suggested_category_code,
        "suggested_category_label": suggested_label,
        "strong_signal": has_strong_signal,
        "emergency_detected": emergency_detected,
        "emergency_reason_summary": emergency_reason_summary,
    }
