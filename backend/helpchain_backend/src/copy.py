# backend/helpchain_backend/src/copy.py
from __future__ import annotations

try:
    from flask_babel import lazy_gettext as _
except Exception:

    def _(s: str) -> str:
        # Fallback when Babel isn't importable (e.g., during isolated tooling runs).
        return s


COPY = {
    "common": {
        "site_name": _("HelpChain"),
    },
    "request": {
        "page_title": _("Подай заявка за помощ"),
        "subtitle": _(
            "Попълни формата и екипът ни ще се свърже с теб възможно най-бързо."
        ),
        "submit": _("Изпрати заявката"),
    },
    "categories": {
        "title": _("Категории помощ"),
    },
}
