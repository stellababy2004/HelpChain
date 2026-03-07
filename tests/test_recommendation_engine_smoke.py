from __future__ import annotations

from types import SimpleNamespace

from backend.helpchain_backend.src.services.recommendation_engine import (
    compute_recommendation,
)


def _req(*, risk_level: str = "standard", signals=None):
    return SimpleNamespace(risk_level=risk_level, risk_signals=signals)


def test_recommendation_violence_escalates_protection():
    out = compute_recommendation(_req(signals=["violence", "no_owner"]))
    assert out["recommended_action"] == "protection_escalation"
    assert out["recommended_pathway"] == "protection"
    assert out["recommended_priority_window"] == "today"


def test_recommendation_critical_no_owner_assigns_immediately():
    out = compute_recommendation(_req(risk_level="critical", signals=["no_owner"]))
    assert out["recommended_action"] == "assign_immediately"
    assert out["recommended_pathway"] == "social_coordination"
    assert out["recommended_priority_window"] == "today"


def test_recommendation_logement_routes_to_housing():
    out = compute_recommendation(_req(signals=["logement"]))
    assert out["recommended_action"] == "route_to_housing_partner"
    assert out["recommended_pathway"] == "housing_support"
    assert out["recommended_priority_window"] == "24h"


def test_recommendation_default_path():
    out = compute_recommendation(_req(signals=[]))
    assert out["recommended_action"] == "routine_queue"
    assert out["recommended_pathway"] == "general_support"
    assert out["recommended_priority_window"] == "this_week"
