from backend.models import UiTranslation, UiTranslationFreeze, db


def test_translation_freeze_blocks_create_bulk_delete_but_allows_update(
    authenticated_admin_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "superadmin",
    )

    activate = authenticated_admin_client.post(
        "/admin/translations/freeze",
        data={"action": "activate", "release_tag": "v2.1", "format": "json"},
    )
    assert activate.status_code == 200
    payload = activate.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["is_active"] is True

    row = UiTranslationFreeze.query.first()
    assert row is not None
    assert row.is_active is True

    existing = UiTranslation(key="case_assign", locale="de", text="Fall zuweisen")
    db.session.add(existing)
    db.session.commit()

    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "ops",
    )

    update_existing = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "case_assign", "locale": "de", "text": "Fall zuordnen"},
        follow_redirects=True,
    )
    assert update_existing.status_code == 200
    updated = UiTranslation.query.filter_by(key="case_assign", locale="de").first()
    assert updated is not None
    assert updated.text == "Fall zuordnen"

    create_new = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={
            "key": "new_release_label",
            "locale": "de",
            "text": "Neue Freigabe",
            "format": "json",
        },
    )
    assert create_new.status_code == 423
    create_payload = create_new.get_json()
    assert create_payload is not None
    assert create_payload["error"] == "translation_frozen"

    bulk = authenticated_admin_client.post(
        "/admin/translations/bulk-suggest-apply",
        data={"locale": "de", "view": "ops", "format": "json"},
    )
    assert bulk.status_code == 423
    bulk_payload = bulk.get_json()
    assert bulk_payload is not None
    assert bulk_payload["error"] == "translation_frozen"

    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "superadmin",
    )

    delete_resp = authenticated_admin_client.post(
        "/admin/translations/delete",
        data={"key": "case_assign", "locale": "de", "format": "json"},
    )
    assert delete_resp.status_code == 423
    delete_payload = delete_resp.get_json()
    assert delete_payload is not None
    assert delete_payload["error"] == "translation_frozen"
