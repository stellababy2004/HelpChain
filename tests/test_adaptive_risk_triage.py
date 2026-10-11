from pathlib import Path

from jinja2 import Environment

from backend.helpchain_backend.src.services.adaptive_experience import (
    MODULE_REGISTRY,
    adaptive_modules,
    modules_for_capabilities,
)


REQUEST = Path(
    "templates/admin/request_details.html"
).read_text(encoding="utf-8")


class Structure:
    def __init__(self, organization_type, capabilities_json=None):
        self.organization_type = organization_type
        self.capabilities_json = capabilities_json


def test_risk_triage_module_is_registered():
    assert "risk_triage" in MODULE_REGISTRY


def test_social_support_gets_risk_triage():
    assert "risk_triage" in modules_for_capabilities(
        ["social_support"]
    )


def test_emergency_triage_gets_risk_triage():
    assert "risk_triage" in modules_for_capabilities(
        ["emergency_triage"]
    )


def test_child_support_gets_risk_triage():
    assert "risk_triage" in modules_for_capabilities(
        ["child_support"]
    )


def test_case_management_gets_risk_triage():
    assert "risk_triage" in modules_for_capabilities(
        ["case_management"]
    )


def test_food_assistance_does_not_get_risk_triage():
    assert "risk_triage" not in modules_for_capabilities(
        ["food_assistance"]
    )


def test_school_default_gets_risk_triage():
    modules = adaptive_modules(
        Structure("school")
    )
    assert "risk_triage" in modules


def test_ccas_default_gets_risk_triage():
    modules = adaptive_modules(
        Structure("ccas")
    )
    assert "risk_triage" in modules


def test_global_admin_gets_risk_triage():
    modules = adaptive_modules(
        None,
        global_admin=True,
    )
    assert "risk_triage" in modules


def test_request_risk_ui_is_adaptive():
    assert REQUEST.count(
        "adaptive_module_enabled('risk_triage')"
    ) == 1
    assert "Moteur de risque social" in REQUEST


def test_request_template_remains_valid():
    Environment().parse(REQUEST)


def test_existing_mobilisation_guards_remain():
    assert REQUEST.count(
        "adaptive_module_enabled('mobilisation')"
    ) == 3
