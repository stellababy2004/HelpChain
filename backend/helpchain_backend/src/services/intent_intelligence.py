from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from backend.helpchain_backend.src.services.analytics_v2 import canonical_event_type


COMMERCIAL_PAGES = {
    "/offre": 12,
    "/demo": 12,
    "/demander-acces": 15,
    "/deploiement": 10,
    "/professionnels": 8,
    "/professionnels/pilote": 15,
    "/pour-les-structures": 8,
}

STRONG_COMMERCIAL_PAGES = {
    "/offre",
    "/demo",
    "/demander-acces",
    "/professionnels/pilote",
}

EVENT_WEIGHTS = {
    "cta_click": 12,
    "form_started": 15,
    "form_abandoned": 5,
    "form_submitted": 30,
}

MAX_INTENT_SCORE = 100


@dataclass(frozen=True)
class IntentResult:
    score: int
    level: str
    reasons: tuple[str, ...]
    event_count: int
    session_count: int
    commercial_page_count: int
    last_activity_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": list(self.reasons),
            "event_count": self.event_count,
            "session_count": self.session_count,
            "commercial_page_count": self.commercial_page_count,
            "last_activity_at": (
                self.last_activity_at.isoformat()
                if self.last_activity_at is not None
                else None
            ),
        }


def _path_only(page_url: str | None) -> str:
    if not page_url:
        return "/"

    value = str(page_url).strip()
    if "://" in value:
        try:
            from urllib.parse import urlparse

            value = urlparse(value).path
        except ValueError:
            return "/"

    value = value.split("?", 1)[0].split("#", 1)[0]
    if not value.startswith("/"):
        value = f"/{value}"

    if len(value) > 1:
        value = value.rstrip("/")

    return value or "/"


def _event_properties(event: Any) -> dict[str, Any]:
    raw = getattr(event, "properties_json", None)
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(parsed, dict):
        return {}

    props = parsed.get("props")
    return props if isinstance(props, dict) else {}


def _event_type(event: Any) -> str:
    return canonical_event_type(getattr(event, "event_type", None))


def _event_time(event: Any) -> datetime | None:
    value = getattr(event, "created_at", None)
    return value if isinstance(value, datetime) else None


def _intent_level(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 40:
        return "warm"
    if score >= 15:
        return "engaged"
    return "low"


def calculate_intent_score(
    events: Iterable[Any],
    *,
    now: datetime | None = None,
) -> IntentResult:
    event_list = list(events)
    now = now or datetime.now(UTC).replace(tzinfo=None)

    score = 0
    reasons: list[str] = []
    sessions: set[str] = set()
    commercial_pages: set[str] = set()
    strong_pages: set[str] = set()
    event_types: list[str] = []
    timestamps: list[datetime] = []

    for event in event_list:
        session_id = getattr(event, "user_session", None)
        if session_id:
            sessions.add(str(session_id))

        created_at = _event_time(event)
        if created_at is not None:
            timestamps.append(created_at)

        canonical_type = _event_type(event)
        event_types.append(canonical_type)

        path = _path_only(getattr(event, "page_url", None))
        if path in COMMERCIAL_PAGES:
            commercial_pages.add(path)
            if path in STRONG_COMMERCIAL_PAGES:
                strong_pages.add(path)

        # Parse properties now so Phase 2 remains compatible with
        # canonical analytics payloads and can be extended safely.
        _event_properties(event)

    # Commercial browsing: reward breadth, but cap it so page refreshing
    # cannot create a hot lead.
    page_points = min(
        30,
        sum(COMMERCIAL_PAGES[path] for path in commercial_pages),
    )
    if page_points:
        score += page_points
        reasons.append(
            f"commercial_pages:{len(commercial_pages)} (+{page_points})"
        )

    # Repeat sessions are a strong independent signal.
    if len(sessions) >= 2:
        repeat_points = min(20, 8 + ((len(sessions) - 2) * 4))
        score += repeat_points
        reasons.append(
            f"repeat_sessions:{len(sessions)} (+{repeat_points})"
        )

    # Conversion actions are weighted independently from page browsing.
    for event_name in ("cta_click", "form_started", "form_abandoned", "form_submitted"):
        count = event_types.count(event_name)
        if not count:
            continue

        # Count the signal once. Repeated clicking/submitting must not
        # artificially inflate intent.
        points = EVENT_WEIGHTS[event_name]
        score += points
        reasons.append(f"{event_name}:{count} (+{points})")

    # Multiple strong commercial destinations indicate deliberate evaluation.
    if len(strong_pages) >= 2:
        score += 8
        reasons.append(f"strong_page_breadth:{len(strong_pages)} (+8)")

    last_activity = max(timestamps) if timestamps else None

    # Recency only reinforces existing intent; it cannot create intent alone.
    if score > 0 and last_activity is not None:
        age = now - last_activity
        if age.total_seconds() >= 0:
            if age.days <= 1:
                score += 10
                reasons.append("recent_activity:24h (+10)")
            elif age.days <= 7:
                score += 6
                reasons.append("recent_activity:7d (+6)")
            elif age.days <= 30:
                score += 3
                reasons.append("recent_activity:30d (+3)")

    score = max(0, min(MAX_INTENT_SCORE, score))

    return IntentResult(
        score=score,
        level=_intent_level(score),
        reasons=tuple(reasons),
        event_count=len(event_list),
        session_count=len(sessions),
        commercial_page_count=len(commercial_pages),
        last_activity_at=last_activity,
    )
