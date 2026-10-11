from pathlib import Path

from jinja2 import Environment


REQUEST = Path(
    "templates/admin/request_details.html"
).read_text(encoding="utf-8")


def test_request_template_has_valid_jinja():
    Environment().parse(REQUEST)


def test_request_core_remains_present():
    for marker in (
        'id="status-management"',
        "admin.admin_request_add_note",
        "admin.update_status",
        "admin.admin_request_assign",
        "admin.admin_request_refer",
    ):
        assert marker in REQUEST


def test_mobilisation_has_three_adaptive_guards():
    assert REQUEST.count(
        "adaptive_module_enabled('mobilisation')"
    ) == 3


def test_mobilisation_section_is_preserved():
    for marker in (
        'id="matching-mobilisation"',
        "hc-main-block--mobilization",
        "hc-main-block--matched-volunteers",
        "hc-main-block--volunteer-signals",
        "hc-main-block--volunteer-actions",
        "hc-main-block--interests",
    ):
        assert marker in REQUEST


def test_volunteer_drawer_is_preserved():
    assert 'id="hcVolunteerDrawer"' in REQUEST
    assert 'id="hcDrawerAssignBtn"' in REQUEST


def test_volunteer_javascript_is_preserved():
    assert "js/admin-volunteer-drawer.js" in REQUEST


def test_global_admin_keeps_mobilisation():
    assert REQUEST.count("adaptive_global_admin") >= 3
