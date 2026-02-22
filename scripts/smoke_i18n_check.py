import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

from flask import render_template

from backend.appy import app

STATUS_LABELS = {
    "pending": "Pending",
    "approved": "Approved",
    "in_progress": "In progress",
    "done": "Completed",
    "rejected": "Rejected",
}

r = SimpleNamespace(
    id=123,
    title="Water delivery",
    name="Ivan Ivanov",
    requester_name="Ivan Ivanov",
    status="pending",
    priority="High",
    category="Food",
    created_at=datetime.now(UTC) - timedelta(days=3),
    closed_at=None,
    owner_id=None,
    completed_at=None,
)

ctx = dict(
    STATUS_LABELS=STATUS_LABELS,
    requests=[r],
    status="",
    q="",
    now_aware=datetime.now(UTC),
    now_naive=datetime.utcnow(),
    SLA_WARN_NO_OWNER_DAYS=2,
    SLA_STALE_DAYS=7,
    highlight=None,
)

checks = {
    "admin/analytics": {
        "template": "admin_analytics.html",
        "keys": {
            "bg": {"Export CSV": "Експорт CSV"},
            "fr": {"Export CSV": "Exporter en CSV"},
        },
    },
    "export-data": {
        "template": "export_data.html",
        "keys": {
            "bg": {"Export data": "Експорт данни", "CSV": "CSV"},
            "fr": {"Export data": "Exporter des données", "CSV": "CSV"},
        },
    },
    "admin/requests": {
        "template": "admin/requests.html",
        "keys": {
            "bg": {
                "Filter": "Филтрирай",
                "Pending": "Чакащи",
                "No results.": "Няма резултати.",
            },
            "fr": {
                "Filter": "Filtrer",
                "Pending": "En attente",
                "No results.": "Aucun résultat.",
            },
        },
    },
}

for page, info in checks.items():
    tpl = info["template"]
    print("\n" + "=" * 20 + f" PAGE: {page} ({tpl}) " + "=" * 20 + "\n")
    for lang in ("fr", "bg"):
        with app.test_request_context("/", headers={"Accept-Language": lang}):
            try:
                out = render_template(tpl, **ctx)
            except Exception as e:
                print(f"{lang}: render ERROR: {e}")
                continue
            print(f"{lang}:")
            missing = []
            for key, expected in info["keys"][lang].items():
                if expected in out:
                    print(f"  {key} -> {expected}: present")
                else:
                    print(f"  {key} -> {expected}: MISSING")
                    missing.append((key, expected))
            # show small snippets for missing
            for key, expected in missing:
                idx = out.find(expected)
                if idx == -1:
                    # try find the English msgid
                    idx = out.find(key)
                snippet = (
                    out[max(0, idx - 60) : idx + 60] if idx != -1 else "[not found]"
                )
                print(f"    snippet: {snippet}")

print("\nCombined smoke render complete.")
