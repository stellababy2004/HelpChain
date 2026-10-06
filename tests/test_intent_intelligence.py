from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.helpchain_backend.src.services.intent_intelligence import (
    calculate_intent_score,
)


NOW = datetime(2026, 10, 6, 9, 30)


def event(
    event_type="page_view",
    page_url="/",
    session_id="aud_1",
    created_at=None,
):
    return SimpleNamespace(
        event_type=event_type,
        page_url=page_url,
        user_session=session_id,
        created_at=created_at or NOW,
        properties_json=None,
    )


def test_random_page_view_stays_low():
    result = calculate_intent_score(
        [event(page_url="/")],
        now=NOW,
    )

    assert result.score == 0
    assert result.level == "low"


def test_single_cta_click_is_not_hot():
    result = calculate_intent_score(
        [event(event_type="cta_click", page_url="/")],
        now=NOW,
    )

    assert result.score < 70
    assert result.level != "hot"
    assert any("cta_click" in reason for reason in result.reasons)


def test_repeat_commercial_interest_becomes_hot():
    events = [
        event(page_url="/offre", session_id="aud_1", created_at=NOW - timedelta(days=3)),
        event(page_url="/demo", session_id="aud_1", created_at=NOW - timedelta(days=3)),
        event(page_url="/demander-acces", session_id="aud_2", created_at=NOW),
        event(event_type="cta_click", page_url="/demo", session_id="aud_2", created_at=NOW),
        event(event_type="form_started", page_url="/demo", session_id="aud_2", created_at=NOW),
    ]

    result = calculate_intent_score(events, now=NOW)

    assert result.score >= 70
    assert result.level == "hot"
    assert result.session_count == 2
    assert result.commercial_page_count == 3
    assert any("repeat_sessions" in reason for reason in result.reasons)


def test_intent_score_is_capped_at_100():
    events = [
        event(page_url="/offre", session_id="aud_1"),
        event(page_url="/demo", session_id="aud_2"),
        event(page_url="/demander-acces", session_id="aud_3"),
        event(page_url="/professionnels/pilote", session_id="aud_4"),
        event(event_type="cta_click", page_url="/demo", session_id="aud_4"),
        event(event_type="form_started", page_url="/demo", session_id="aud_4"),
        event(event_type="form_submitted", page_url="/demo", session_id="aud_4"),
    ]

    result = calculate_intent_score(events, now=NOW)

    assert result.score == 100
    assert result.level == "hot"
