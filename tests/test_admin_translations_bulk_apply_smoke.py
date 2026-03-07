from backend.models import UiTranslation


def test_admin_translations_bulk_apply_ops(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_key_registry",
        lambda: [
            {
                "key": "case_intelligence_next_action",
                "default": "Next action",
                "domain": "admin_case",
                "kind": "tkey",
                "tier": "core",
            },
            {
                "key": "submit_request",
                "default": "Submit",
                "domain": "buttons",
                "kind": "tkey",
                "tier": "core",
            },
            {
                "key": "inv_long_copy",
                "default": "Long paragraph",
                "domain": "public",
                "kind": "msgid",
                "tier": "inventory",
            },
        ],
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_domains",
        lambda: {"core_ops_domains": ["admin_case", "buttons"]},
    )

    before_missing = authenticated_admin_client.get(
        "/admin/translations?locale=de&only_missing=1&view=ops"
    )
    assert before_missing.status_code == 200
    before_body = before_missing.get_data(as_text=True)
    assert "case_intelligence_next_action" in before_body
    assert "submit_request" in before_body

    resp = authenticated_admin_client.post(
        "/admin/translations/bulk-suggest-apply",
        data={"locale": "de", "view": "ops", "limit": "50", "format": "json"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["applied"] >= 1
    assert payload["view"] == "ops"
    assert payload["locale"] == "de"

    rows = UiTranslation.query.filter_by(locale="de").all()
    assert len(rows) >= 1

    after_missing = authenticated_admin_client.get(
        "/admin/translations?locale=de&only_missing=1&view=ops"
    )
    assert after_missing.status_code == 200
    after_body = after_missing.get_data(as_text=True)
    assert "No missing keys for this locale." in after_body
