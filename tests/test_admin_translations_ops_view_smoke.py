def test_admin_translations_ops_view_default_filters_domains(authenticated_admin_client, monkeypatch):
    registry = [
        {"key": "k_admin_req", "default": "Req", "domain": "admin_requests", "kind": "msgid", "tier": "core"},
        {"key": "k_public", "default": "Public", "domain": "public", "kind": "msgid", "tier": "core"},
        {"key": "k_inv", "default": "Inventory", "domain": "admin_requests", "kind": "msgid", "tier": "inventory"},
    ]

    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_key_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_domains",
        lambda: {"core_ops_domains": ["admin_requests"]},
    )

    # Default view should be ops, with only_missing showing filtered registry rows.
    resp_ops = authenticated_admin_client.get("/admin/translations?locale=de&only_missing=1")
    assert resp_ops.status_code == 200
    body_ops = resp_ops.get_data(as_text=True)
    assert "k_admin_req" in body_ops
    assert "k_public" not in body_ops
    assert "k_inv" not in body_ops

    resp_core = authenticated_admin_client.get("/admin/translations?locale=de&only_missing=1&view=core")
    assert resp_core.status_code == 200
    body_core = resp_core.get_data(as_text=True)
    assert "k_admin_req" in body_core
    assert "k_public" in body_core
    assert "k_inv" not in body_core

    resp_inventory = authenticated_admin_client.get("/admin/translations?locale=de&only_missing=1&view=inventory")
    assert resp_inventory.status_code == 200
    body_inventory = resp_inventory.get_data(as_text=True)
    assert "k_inv" in body_inventory
    assert "k_admin_req" not in body_inventory

