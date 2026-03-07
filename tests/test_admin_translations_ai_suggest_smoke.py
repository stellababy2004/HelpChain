def test_admin_translations_ai_suggest_uses_hf_when_available(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._ui_registry_get",
        lambda _key: {"default": "Creer un dossier", "domain": "public"},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._hf_translate_fr_to",
        lambda locale, text: "Fall erstellen" if locale == "de" else None,
    )

    resp = authenticated_admin_client.post(
        "/admin/translations/ai-suggest",
        data={"key": "case_create", "locale": "de", "provider": "hf_local"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["provider"] == "hf_local"
    suggestions = payload.get("suggestions") or []
    assert len(suggestions) >= 1
    assert suggestions[0]["text"] == "Fall erstellen"


def test_admin_translations_ai_suggest_falls_back_to_rules(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._ui_registry_get",
        lambda _key: {"default": "Demande", "domain": "public"},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._hf_translate_fr_to",
        lambda locale, text: None,
    )

    resp = authenticated_admin_client.post(
        "/admin/translations/ai-suggest",
        data={"key": "request_label", "locale": "de", "provider": "hf_local"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    suggestions = payload.get("suggestions") or []
    assert len(suggestions) >= 1
