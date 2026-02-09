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

for lang in ("bg", "fr"):
    with app.test_request_context("/", headers={"Accept-Language": lang}):
        out = render_template("admin/requests.html", **ctx)
        print("\n" + "=" * 20 + f" {lang} " + "=" * 20 + "\n")
        # Check localized markers per language
        expected = {
            "bg": {
                "Filter": "Филтрирай",
                "Export CSV": "Експорт CSV",
                "Pending": "Чакащи",
                "No owner": "Няма собственик",
                "No results.": "Няма резултати.",
            },
            "fr": {
                "Filter": "Filtrer",
                "Export CSV": "Exporter en CSV",
                "Pending": "En attente",
                "No owner": "Sans responsable",
                "No results.": "Aucun résultat.",
            },
        }
        for key, val in expected[lang].items():
            present = val in out
            print(f"{key} -> {val}:", "present" if present else "MISSING")
        # print a short slice around the Filter button
        if "Filter" in out:
            i = out.find("Filter")
            print("\n...context around Filter...")
            print(out[max(0, i - 60) : i + 60])
        # print snippet for export_confirm if present
        if "This export contains personal data" in out or "\u26a0" in out:
            i = out.find("This export contains")
            if i == -1:
                i = out.find("\u26a0")
            print("\n...export_confirm snippet...")
            print(out[max(0, i - 80) : i + 80])

print("\nSmoke render complete.")
