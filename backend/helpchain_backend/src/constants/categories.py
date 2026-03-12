from __future__ import annotations

from collections import OrderedDict


# Canonical operational categories (stored as stable internal codes).
REQUEST_CATEGORY_LABELS = OrderedDict(
    [
        ("food", "Aide alimentaire"),
        ("emergency", "Urgence sociale"),
        ("isolation", "Isolement / personne vulnerable"),
        ("violence", "Violence / protection"),
        ("housing", "Logement / hebergement"),
        ("health", "Sante / acces aux soins"),
        ("admin_help", "Aide administrative"),
        ("orientation", "Orientation vers service social"),
    ]
)

# Backward-compatible aliases / historical codes.
REQUEST_CATEGORY_ALIASES: dict[str, str] = {
    "general": "orientation",
    "social": "orientation",
    "medical": "health",
    "tech": "admin_help",
    "admin": "admin_help",
    "other": "orientation",
    "urgence": "emergency",
    "aide_medicale": "health",
    "soutien_social": "orientation",
    "acces_administratif": "admin_help",
    "aide_technique": "admin_help",
    "acces_numerique": "admin_help",
    "aide_alimentaire": "food",
    "hebergement_logement": "housing",
    "hebergement": "housing",
    "logement": "housing",
    "violence_domestique": "violence",
    "protection_violence": "violence",
    "soutien_psychologique": "isolation",
    "техническа помощ": "admin_help",
}

# Labels for legacy values that may still exist in database.
LEGACY_CATEGORY_LABELS: dict[str, str] = {
    "admin": "Aide administrative (legacy)",
    "general": "Orientation vers service social (legacy)",
    "tech": "Aide administrative (legacy)",
    "social": "Orientation vers service social (legacy)",
    "medical": "Sante / acces aux soins (legacy)",
    "other": "Orientation vers service social (legacy)",
}

REQUEST_CATEGORY_CODES = tuple(REQUEST_CATEGORY_LABELS.keys())


def normalize_request_category(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    if value in REQUEST_CATEGORY_LABELS:
        return value
    return REQUEST_CATEGORY_ALIASES.get(value, value)


def request_category_label(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return "—"
    normalized = normalize_request_category(value)
    if normalized in REQUEST_CATEGORY_LABELS:
        return REQUEST_CATEGORY_LABELS[normalized]
    lowered = value.lower()
    if lowered in LEGACY_CATEGORY_LABELS:
        return LEGACY_CATEGORY_LABELS[lowered]
    return value.replace("_", " ").replace("-", " ").strip().title() or value


def request_category_choices() -> list[tuple[str, str]]:
    return [(code, label) for code, label in REQUEST_CATEGORY_LABELS.items()]
