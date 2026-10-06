from types import SimpleNamespace

from backend.helpchain_backend.src.services.sales_priority import (
    calculate_fit_score,
    calculate_priority_score,
)


def test_target_ccas_has_strong_fit():
    prospect = SimpleNamespace(
        organization_name="CCAS Boulogne-Billancourt",
        org_type="CCAS",
        contact_name="Marie Dupont",
        email="marie@example.test",
        city="Boulogne-Billancourt",
        estimated_users=20,
    )

    result = calculate_fit_score(prospect)

    assert result.score >= 70
    assert result.level == "strong"


def test_hot_identified_good_fit_should_be_contacted_today():
    result = calculate_priority_score(
        intent_score=85,
        fit_score=85,
        contactable=True,
        form_submitted=True,
    )

    assert result.score >= 75
    assert result.level == "contact_now"
    assert result.next_best_action == "contact_today"


def test_anonymous_hot_visitor_cannot_be_contact_today():
    result = calculate_priority_score(
        intent_score=95,
        fit_score=0,
        contactable=False,
        form_submitted=False,
    )

    assert result.score <= 49
    assert result.next_best_action == "wait_for_identification"
