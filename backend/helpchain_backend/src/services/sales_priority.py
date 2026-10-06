from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MAX_SCORE = 100

TARGET_ORG_TYPES = {
    "ccas",
    "association",
    "mairie",
    "service social",
}

PUBLIC_OR_SOCIAL_TERMS = (
    "ccas",
    "association",
    "mairie",
    "commune",
    "service social",
    "solidarite",
    "solidarité",
    "social",
)


@dataclass(frozen=True)
class FitResult:
    score: int
    level: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class PriorityResult:
    score: int
    level: str
    reasons: tuple[str, ...]
    next_best_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": list(self.reasons),
            "next_best_action": self.next_best_action,
        }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fit_level(score: int) -> str:
    if score >= 70:
        return "strong"
    if score >= 40:
        return "good"
    if score >= 15:
        return "possible"
    return "unknown"


def _priority_level(score: int) -> str:
    if score >= 75:
        return "contact_now"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def calculate_fit_score(prospect: Any) -> FitResult:
    score = 0
    reasons: list[str] = []

    organization = _text(
        getattr(prospect, "organization", None)
        or getattr(prospect, "organization_name", None)
    )
    org_type = _text(getattr(prospect, "org_type", None)).lower()
    city = _text(getattr(prospect, "city", None))
    email = _text(getattr(prospect, "email", None))
    contact_name = _text(
        getattr(prospect, "full_name", None)
        or getattr(prospect, "contact_name", None)
    )
    profession = _text(getattr(prospect, "profession", None))
    estimated_users = getattr(prospect, "estimated_users", None)

    if organization:
        score += 20
        reasons.append("identified_organization (+20)")

    if org_type in TARGET_ORG_TYPES:
        score += 25
        reasons.append(f"target_org_type:{org_type} (+25)")
    elif organization and any(
        term in organization.lower() for term in PUBLIC_OR_SOCIAL_TERMS
    ):
        score += 20
        reasons.append("target_organization_signal (+20)")

    if contact_name:
        score += 10
        reasons.append("identified_contact (+10)")

    if email:
        score += 10
        reasons.append("contact_email (+10)")

    if city:
        score += 10
        reasons.append("territory_known (+10)")

    if profession:
        score += 10
        reasons.append("professional_role_known (+10)")

    if isinstance(estimated_users, int) and estimated_users > 0:
        score += 15
        reasons.append("deployment_size_known (+15)")

    score = max(0, min(MAX_SCORE, score))

    return FitResult(
        score=score,
        level=_fit_level(score),
        reasons=tuple(reasons),
    )


def calculate_priority_score(
    *,
    intent_score: int,
    fit_score: int,
    contactable: bool,
    form_submitted: bool = False,
) -> PriorityResult:
    intent = max(0, min(MAX_SCORE, int(intent_score)))
    fit = max(0, min(MAX_SCORE, int(fit_score)))

    # Intent carries slightly more weight because recent demonstrated
    # buying/evaluation behaviour should drive sales timing.
    score = round((intent * 0.60) + (fit * 0.40))
    reasons = [
        f"intent:{intent} x0.60",
        f"fit:{fit} x0.40",
    ]

    if form_submitted:
        score += 10
        reasons.append("form_submitted (+10)")

    # Anonymous visitors may have high intent but cannot be contacted.
    if not contactable:
        score = min(score, 49)
        reasons.append("anonymous_not_contactable (cap 49)")

    score = max(0, min(MAX_SCORE, score))
    level = _priority_level(score)

    if not contactable:
        action = "wait_for_identification"
    elif score >= 75:
        action = "contact_today"
    elif score >= 55:
        action = "contact_soon"
    elif score >= 30:
        action = "nurture"
    else:
        action = "monitor"

    return PriorityResult(
        score=score,
        level=level,
        reasons=tuple(reasons),
        next_best_action=action,
    )
