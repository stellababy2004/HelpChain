import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import UTC, datetime, timezone
from types import SimpleNamespace

from flask import render_template

from backend.appy import app

ctx = dict(
    STATUS_LABELS={},
    requests=[],
    status="",
    q="",
    now_aware=datetime.now(UTC),
    now_naive=datetime.utcnow(),
    SLA_WARN_NO_OWNER_DAYS=2,
    SLA_STALE_DAYS=7,
    highlight=None,
)
for lang in ("fr", "bg"):
    with app.test_request_context("/", headers={"Accept-Language": lang}):
        out = render_template("admin/requests.html", **ctx)
        print("\n" + "=" * 20 + f" lang={lang} " + "=" * 20 + "\n")
        if "Няма резултати." in out or "Aucun résultat." in out:
            print("No results. localized: present")
        else:
            print("No results. localized: MISSING")
