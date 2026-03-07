from backend.models import UiTranslation


def test_admin_translations_readonly_cannot_write(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "readonly",
    )

    list_resp = authenticated_admin_client.get("/admin/translations?locale=de")
    assert list_resp.status_code == 200

    upsert_resp = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "submit_request", "locale": "de", "text": "Senden"},
    )
    assert upsert_resp.status_code == 403

    bulk_resp = authenticated_admin_client.post(
        "/admin/translations/bulk-suggest-apply",
        data={"locale": "de", "view": "ops", "format": "json"},
    )
    assert bulk_resp.status_code == 403


def test_admin_translations_ops_can_write_but_cannot_delete(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "ops",
    )

    upsert_resp = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "volunteer_dashboard", "locale": "de", "text": "Freiwilligen-Dashboard"},
        follow_redirects=True,
    )
    assert upsert_resp.status_code == 200

    row = UiTranslation.query.filter_by(key="volunteer_dashboard", locale="de").first()
    assert row is not None

    delete_resp = authenticated_admin_client.post(
        "/admin/translations/delete",
        data={"key": "volunteer_dashboard", "locale": "de"},
    )
    assert delete_resp.status_code == 403
