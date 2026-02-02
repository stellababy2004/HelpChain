# Status single source of truth

from flask_babel import lazy_gettext as _l


REQUEST_STATUS_META = {
    "open": {
        "label": _l("Open"),
        "icon": "bi-inbox",
        "badge_class": "badge bg-primary",
    },
    "in_progress": {
        "label": _l("In progress"),
        "icon": "bi-tools",
        "badge_class": "badge bg-warning text-dark",
    },
    "done": {
        "label": _l("Done"),
        "icon": "bi-check-circle",
        "badge_class": "badge bg-success",
    },
    "cancelled": {
        "label": _l("Cancelled"),
        "icon": "bi-x-circle",
        "badge_class": "badge bg-secondary",
    },
}

REQUEST_STATUS_ALLOWED = set(REQUEST_STATUS_META.keys())
REQUEST_STATUS_ORDER = ["open", "in_progress", "done", "cancelled"]

# Legacy aliases -> canonical statuses (no migrations)
REQUEST_STATUS_ALIASES = {
    "approved": "in_progress",   # legacy approved behaves like in_progress
    "rejected": "cancelled",     # legacy rejected behaves like cancelled
    "pending": "open",
}


def normalize_request_status(s: str | None) -> str:
    s = (s or "").strip().lower()
    return REQUEST_STATUS_ALIASES.get(s, s)

