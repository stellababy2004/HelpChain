from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.helpchain_backend.src.routes.admin_cases import build_case_copilot
from backend.helpchain_backend.src.services.case_assistant import (
    build_case_assistant_recommendation,
)


# Keep the fixture aligned with the production helper's live UTC clock so the
# "normal" branch remains recent instead of becoming stale as time passes.
NOW = datetime.now(UTC)


def _case(**overrides):
    values = {
        "status": "in_progress",
        "priority": "normal",
        "risk_score": 10,
        "owner_user_id": 7,
        "created_at": NOW - timedelta(hours=4),
        "updated_at": NOW - timedelta(hours=1),
        "last_activity_at": NOW - timedelta(hours=1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides):
    values = {
        "status": "in_progress",
        "priority": "normal",
        "risk_score": 10,
        "risk_level": "normal",
        "created_at": NOW - timedelta(hours=4),
        "category": "orientation",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_case_copilot_main_branches_are_deterministic_and_explainable():
    normal = build_case_copilot(_case(), _request())
    unassigned = build_case_copilot(_case(owner_user_id=None), _request())
    stale = build_case_copilot(
        _case(last_activity_at=NOW - timedelta(hours=73)), _request()
    )
    urgent = build_case_copilot(
        _case(priority="critical", risk_score=90), _request(priority="critical")
    )
    closed = build_case_copilot(
        _case(status="closed"), _request(status="closed")
    )

    assert normal["attention_level"] == "green"
    assert "standard" in normal["recommended_action"].lower()
    assert unassigned["recommended_action"] == "Attribuer un référent aujourd'hui."
    assert stale["attention_level"] == "orange"
    assert "Relancer" in stale["recommended_action"]
    assert urgent["attention_level"] == "red"
    assert "priorit" in urgent["recommended_action"].lower()
    assert closed["recommended_action"] == "Conserver l'historique et vérifier la clôture."

    for result in (normal, unassigned, stale, urgent, closed):
        assert result["reason"]
        assert result["summary_points"]


def test_case_intelligence_recommendation_is_read_only():
    case = _case(owner_user_id=None)
    request = _request(risk_level="critical")
    before_case = vars(case).copy()
    before_request = vars(request).copy()

    build_case_copilot(case, request)
    build_case_assistant_recommendation(
        case,
        request,
        {"risk_label": "CRITICAL", "derived_priority": "critical"},
        [],
    )

    assert vars(case) == before_case
    assert vars(request) == before_request
