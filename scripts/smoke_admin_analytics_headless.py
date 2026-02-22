import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone
from types import SimpleNamespace

from flask import render_template

from backend.appy import app

ctx = dict(
    export_confirm="\n".join(
        [
            "⚠️ This export contains personal data.",
            "Internal use only.",
            "Are you sure you want to continue?",
        ]
    ),
    trends_data=[
        {"date": "2026-01-01", "value": 10},
        {"date": "2026-01-02", "value": 12},
    ],
    category_stats={"Requests": 123, "Volunteers": 45},
    predictions=[{"label": "uptick", "score": 0.7}],
    filters={},
    report_links=[],
    stats={"total_requests": 100},
)

# Provide dashboard_stats used heavily in the template
dashboard_stats = {
    "overview": {
        "total_page_views": 150,
        "conversion_rate": 12.5,
        "avg_session_time": 5.4,
        "unique_visitors": 80,
        "bounce_rate": 32,
    },
    "performance_metrics": {
        "endpoint_performance": [{"endpoint": "/api/foo", "latency": 120}]
    },
    "chatbot_analytics": {
        "total_conversations": 42,
        "average_rating": 4.2,
    },
}

ctx["dashboard_stats"] = dashboard_stats

for lang in ("fr", "bg"):
    with app.test_request_context("/", headers={"Accept-Language": lang}):
        try:
            out = render_template("admin_analytics.html", **ctx)
            present = "Export CSV" not in out and (
                "Exporter en CSV" in out or "Експорт CSV" in out
            )
            print("\n" + "=" * 20 + f" lang={lang} " + "=" * 20 + "\n")
            print("Export CSV localized:", "yes" if present else "no")
            # quick checks
            print("Snippet around export button:")
            i = out.find("export-btn")
            print(out[max(0, i - 100) : i + 200])
        except Exception as e:
            print("\nERROR rendering admin_analytics for", lang, e)

print("\nheadless analytics check complete")
