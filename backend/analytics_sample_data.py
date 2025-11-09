"""Utility helpers for generating sample analytics data.

These helpers are used by Celery scheduled tasks, tests,
and local development scripts to keep the analytics pipeline
populated with realistic events even on fresh databases.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta

from backend.extensions import db  # canonical import

try:
    from backend.models_with_analytics import AnalyticsEvent, UserBehavior
except ImportError:  # pragma: no cover
    from backend.models_with_analytics import AnalyticsEvent, UserBehavior  # type: ignore

SAMPLE_PREFIX = "[SAMPLE]"
DEFAULT_EVENT_TYPES: tuple[str, ...] = (
    "page_view",
    "form_interaction",
    "feature_usage",
    "search",
    "login",
    "registration",
)
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "navigation",
    "volunteer",
    "admin",
    "engagement",
    "conversion",
)
DEFAULT_PAGES: tuple[str, ...] = (
    "/",
    "/analytics",
    "/volunteers",
    "/help-requests",
    "/reports",
    "/profile",
)
DEFAULT_FEATURES: tuple[str, ...] = (
    "search",
    "volunteer_registration",
    "admin_panel",
    "messaging",
    "notifications",
)


def _get_session():
    if db is None:
        raise RuntimeError("Database instance is not configured")
    return db.session


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


def generate_sample_analytics_events(
    db_session=None,
    *,
    days: int = 5,
    events_per_day: int = 48,
    force: bool = False,
) -> int:
    """Generate deterministic sample analytics events.

    Args:
        db_session: Optional SQLAlchemy session. Defaults to the global session.
        days: Number of days to span the generated events across.
        events_per_day: Target number of events for each day. Recent days
            receive slightly more traffic to create trends and anomalies.
        force: When False, skip generation if recent sample events already exist.

    Returns:
        int: Number of AnalyticsEvent records created.
    """

    session = db_session or _get_session()

    now = utc_now()
    window_start = now - timedelta(days=days)

    existing_query = (
        session.query(AnalyticsEvent.id)
        .filter(AnalyticsEvent.event_label.like(f"{SAMPLE_PREFIX}%"))
        .filter(AnalyticsEvent.created_at >= window_start)
    )

    if not force and existing_query.first():
        return 0

    created_events = 0
    random.seed(42)  # Stable pseudo-random sequence for reproducibility

    for day_index in range(days):
        # Ensure rising traffic for newer days so anomaly detection has signal
        day_multiplier = 1 + 0.35 * (days - day_index - 1)
        target_events = max(int(events_per_day * day_multiplier), events_per_day)
        day_start = now - timedelta(days=day_index)

        sample_sessions = [f"sample_session_{day_index}_{n}" for n in range(6)]

        for event_number in range(target_events):
            timestamp = day_start - timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )

            session_id = random.choice(sample_sessions)
            feature = random.choice(DEFAULT_FEATURES)
            event_type = random.choice(DEFAULT_EVENT_TYPES)
            category = random.choice(DEFAULT_CATEGORIES)

            has_error = event_number % max(8 - day_index, 3) == 0 and day_index == 0
            details = (
                f"{SAMPLE_PREFIX} error spike detected"
                if has_error and event_type != "login"
                else f"{SAMPLE_PREFIX} {feature}"
            )

            event = AnalyticsEvent(
                event_type=event_type,
                event_category=category,
                event_action="auto_sample",
                event_label=details,
                event_value=random.randint(1, 100),
                user_session=session_id,
                user_type=random.choice(["guest", "volunteer", "admin"]),
                user_ip=f"192.0.2.{random.randint(10, 200)}",
                user_agent="SampleAgent/1.0",
                referrer=random.choice([None, "https://helpchain.bg", "direct"]),
                page_url=random.choice(DEFAULT_PAGES),
                page_title=f"Sample page {event_number % 10}",
                load_time=round(random.uniform(0.2, 2.5), 3),
                screen_resolution=random.choice(["1920x1080", "1366x768", "1536x864"]),
                device_type=random.choice(["desktop", "mobile", "tablet"]),
                created_at=timestamp,
            )

            session.add(event)
            _upsert_user_behavior(session, session_id, timestamp, feature)
            created_events += 1

    session.commit()
    return created_events


def _upsert_user_behavior(
    session, session_id: str, timestamp: datetime, feature: str
) -> None:
    """Create or update a lightweight user behavior record for the session."""

    behavior = session.query(UserBehavior).filter_by(session_id=session_id).first()

    if behavior is None:
        behavior = UserBehavior(
            session_id=session_id,
            user_type=random.choice(["guest", "volunteer", "admin"]),
            entry_page=random.choice(DEFAULT_PAGES),
            ip_address=f"198.51.100.{random.randint(1, 200)}",
            device_info=random.choice(["Chrome", "Firefox", "Safari"]),
            location=random.choice(["Sofia", "Plovdiv", "Varna", "Burgas"]),
            pages_sequence="[]",
        )
        session.add(behavior)

    behavior.last_activity = timestamp
    behavior.pages_visited = (behavior.pages_visited or 0) + 1
    behavior.exit_page = random.choice(DEFAULT_PAGES)

    # Keep the last 10 visited pages in the sequence JSON string

    sequence: list[dict] = []
    if behavior.pages_sequence:
        try:
            sequence = json.loads(behavior.pages_sequence)
        except json.JSONDecodeError:
            sequence = []

    sequence = list(sequence)
    sequence.append(
        {
            "url": behavior.exit_page,
            "feature": feature,
            "ts": timestamp.isoformat(),
        }
    )
    behavior.pages_sequence = json.dumps(sequence[-10:])
