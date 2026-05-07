import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

from backend.appy import app
from backend.extensions import db
from backend.models_with_analytics import AnalyticsEvent


def normalize_path(value):
    if not value:
        return "/"

    try:
        parsed = urlparse(value)
        return parsed.path or "/"
    except Exception:
        return value


def classify_intent(score, paths):
    paths_joined = " ".join(paths)

    if (
        score >= 80
        or "/demo" in paths_joined
        or "form_start" in paths_joined
    ):
        return "high"

    if score >= 40:
        return "medium"

    return "low"


with app.app_context():

    since = datetime.utcnow() - timedelta(days=7)

    events = (
        db.session.query(AnalyticsEvent)
        .filter(AnalyticsEvent.created_at >= since)
        .order_by(AnalyticsEvent.created_at.asc())
        .all()
    )

    sessions = defaultdict(list)

    for event in events:
        session_key = (
            event.user_session
            or event.user_ip
            or "anonymous"
        )

        sessions[session_key].append(event)

    print()
    print("=" * 80)
    print("HELPCHAIN SESSION INTELLIGENCE")
    print("=" * 80)
    print()

    for session_id, rows in sessions.items():

        score = 0
        paths = []
        event_types = []

        for row in rows:

            path = normalize_path(row.page_url)

            if path:
                paths.append(path)

            event_type = row.event_type or "unknown"
            event_types.append(event_type)

            if event_type == "page_view":
                score += 1

            if event_type == "page_engagement":
                score += 10

            if event_type == "cta_demo_click":
                score += 25

            if event_type == "form_start":
                score += 40

            if event_type == "demo_form_submit":
                score += 100

            if "/offre" in path:
                score += 10

            if "/deploiement" in path:
                score += 15

            if "/demo" in path:
                score += 20

        unique_paths = []

        for p in paths:
            if not unique_paths or unique_paths[-1] != p:
                unique_paths.append(p)

        intent = classify_intent(score, unique_paths)

        print(f"SESSION: {session_id[:16]}")
        print(f"INTENT : {intent.upper()}")
        print(f"SCORE  : {score}")
        print("PATH   :")
        print("  " + " -> ".join(unique_paths[:12]))

        print("EVENTS :")
        print("  " + ", ".join(event_types[:12]))

        print("-" * 80)


