import re

import pytest

pytestmark = pytest.mark.spine


@pytest.fixture
def admin_login(authenticated_admin_client):
    return authenticated_admin_client


def _extract_bulk_actions(html: str) -> list[str]:
    m = re.search(
        r'<select[^>]+id="hcBulkAction"[^>]*>(.*?)</select>',
        html,
        flags=re.S | re.I,
    )
    assert m, "Bulk action <select id='hcBulkAction'> not found in HTML"
    block = m.group(1)
    return re.findall(r"<option[^>]*>(.*?)</option>", block, flags=re.I)


def _extract_bulk_action_values(html: str) -> list[str]:
    m = re.search(
        r'<select[^>]+id="hcBulkAction"[^>]*>(.*?)</select>',
        html,
        flags=re.S | re.I,
    )
    assert m, "Bulk action <select id='hcBulkAction'> not found in HTML"
    block = m.group(1)
    return re.findall(r'<option[^>]+value="([^"]*)"', block, flags=re.I)


def test_bulk_actions_dropdown_has_expected_options(admin_login):
    r = admin_login.get("/admin/requests")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="hcBulkAction"' in html

    option_values = _extract_bulk_action_values(html)

    expected_values = [
        "",
        "claim_me",
        "open",
        "copy_ids",
        "copy_links",
        "nudge",
        "status:pending",
        "status:in_progress",
        "status:done",
        "status:rejected",
    ]

    for value in expected_values:
        assert value in option_values, f"Missing option value: {value}"

    assert set(option_values) >= set(expected_values)
