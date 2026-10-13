import json
from types import SimpleNamespace

from backend.helpchain_backend.src.services.adaptive_experience import (
    CCAS_DASHBOARD_PROFILE,
    GENERIC_DASHBOARD_PROFILE,
    GLOBAL_ADMIN_MODULES,
    SCHOOL_DASHBOARD_PROFILE,
    adaptive_modules,
    module_enabled,
    organization_capabilities,
    resolve_dashboard_profile,
)


def structure(org_type=None, capabilities=None):
    return SimpleNamespace(
        organization_type=org_type,
        capabilities_json=(
            json.dumps(capabilities)
            if capabilities is not None
            else None
        ),
    )


def test_school_uses_existing_default_capabilities():
    item = structure("school")

    assert organization_capabilities(item) == (
        "child_support",
        "education_support",
    )

    modules = adaptive_modules(item)

    assert modules == (
        "home",
        "calendar",
        "requests",
        "cases",
        "referrals",
        "risk_triage",
    )


def test_ccas_gets_social_operational_experience():
    modules = adaptive_modules(structure("ccas"))

    assert "home" in modules
    assert "workspace" in modules
    assert "requests" in modules
    assert "cases" in modules
    assert "referrals" in modules
    assert "notifications" in modules

    assert "platform" not in modules
    assert "security" not in modules


def test_municipality_gets_territorial_modules():
    modules = adaptive_modules(structure("municipality"))

    assert "pilotage" in modules
    assert "maps" in modules
    assert "reports" in modules
    assert "requests" in modules
    assert "cases" in modules


def test_configured_capabilities_override_type_defaults():
    item = structure(
        "school",
        ["case_management"],
    )

    assert organization_capabilities(item) == ("case_management",)

    modules = adaptive_modules(item)

    assert "workspace" in modules
    assert "professionals" in modules


def test_unknown_organization_is_safe_by_default():
    modules = adaptive_modules(structure("something_unknown"))

    assert modules == ("home", "calendar")


def test_global_admin_keeps_full_cockpit():
    modules = adaptive_modules(
        structure("school"),
        global_admin=True,
    )

    assert modules == GLOBAL_ADMIN_MODULES
    assert "platform" in modules
    assert "security" in modules
    assert "pilotage" in modules


def test_module_enabled_helper():
    item = structure("school")

    assert module_enabled(item, "requests")
    assert module_enabled(item, "cases")
    assert not module_enabled(item, "platform")


def test_unknown_organization_uses_generic_dashboard_profile():
    assert resolve_dashboard_profile(structure("unknown")) is GENERIC_DASHBOARD_PROFILE
    assert resolve_dashboard_profile(None) is GENERIC_DASHBOARD_PROFILE


def test_school_uses_school_dashboard_profile():
    profile = resolve_dashboard_profile(structure("school"))

    assert profile is SCHOOL_DASHBOARD_PROFILE
    assert profile.key == "school"
    assert profile.show_operational_intelligence is False
    assert tuple(metric.key for metric in profile.hero_metrics) == (
        "priority",
        "follow_up",
        "unassigned",
        "stale",
    )


def test_ccas_uses_ccas_dashboard_profile():
    profile = resolve_dashboard_profile(structure("ccas"))

    assert profile is CCAS_DASHBOARD_PROFILE
    assert profile.key == "ccas"
    assert profile.hero_title == "Tableau de bord du CCAS"
    assert profile.show_operational_intelligence is True
