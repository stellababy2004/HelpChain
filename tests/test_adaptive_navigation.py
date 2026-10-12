from pathlib import Path

from backend.helpchain_backend.src.services.adaptive_experience import (
    adaptive_modules,
)


TEMPLATE = Path("templates/layouts/admin_workspace.html")


class Structure:
    def __init__(self, organization_type, capabilities_json=None):
        self.organization_type = organization_type
        self.capabilities_json = capabilities_json


def test_school_gets_simple_navigation():
    modules = adaptive_modules(Structure("school"))

    assert modules == (
        "home",
        "requests",
        "cases",
        "referrals",
        "risk_triage",
    )


def test_municipality_gets_operational_pilotage():
    modules = adaptive_modules(Structure("municipality"))

    for module in (
        "workspace",
        "requests",
        "cases",
        "referrals",
        "pilotage",
        "maps",
        "reports",
    ):
        assert module in modules


def test_navigation_uses_adaptive_guards():
    source = TEMPLATE.read_text(encoding="utf-8")

    for module in (
        "workspace",
        "requests",
        "cases",
        "referrals",
        "notifications",
        "pilotage",
        "reports",
        "connectors",
        "security",
        "platform",
    ):
        assert f"adaptive_module_enabled('{module}')" in source


def test_founder_tools_remain_global_only():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "can_access_professional_leads = adaptive_global_admin" in source
    assert "can_access_global_analytics = adaptive_global_admin" in source

    conversion = source.index('href="/admin/conversion-dashboard"')
    guard = source.rfind(
        "{% if adaptive_global_admin %}",
        0,
        conversion,
    )

    assert guard != -1
    assert conversion - guard < 500


def test_home_remains_available():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "url_for('admin.admin_home')" in source

def test_adaptive_context_exposes_organization_type():
    source = Path(
        "backend/helpchain_backend/src/app.py"
    ).read_text(encoding="utf-8")

    assert '"adaptive_organization_type": organization_type' in source
    assert 'getattr(structure, "organization_type", None)' in source
