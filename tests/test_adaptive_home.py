from pathlib import Path
from jinja2 import Environment

HOME_PATH = Path("templates/admin/admin_home.html")
HOME = HOME_PATH.read_text(encoding="utf-8")


def test_home_jinja_is_valid():
    Environment().parse(HOME)


def test_core_requests_remain_available():
    assert "admin.admin_requests" in HOME


def test_notifications_are_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('notifications')"
    ) == 3
    assert "admin.admin_notifications_list" in HOME


def test_security_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('security')"
    ) == 3
    assert "admin.admin_security" in HOME


def test_platform_action_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('platform')"
    ) == 1
    assert "admin.admin_roles" in HOME


def test_pilotage_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('pilotage')"
    ) == 2
    assert "admin.admin_risk_map" in HOME
    assert "admin.admin_professionals_map" in HOME


def test_global_admin_escape_hatch_exists():
    assert HOME.count("adaptive_global_admin") >= 9
