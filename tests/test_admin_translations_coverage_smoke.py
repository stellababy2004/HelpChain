from backend.models import UiTranslation, db


def test_admin_translations_coverage_json_structure(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_key_registry",
        lambda: [
            {"key": "k_public", "default": "Public", "domain": "public_nav", "kind": "tkey", "tier": "core"},
            {"key": "k_vol", "default": "Volunteer", "domain": "volunteer_nav", "kind": "tkey", "tier": "core"},
            {"key": "k_admin", "default": "Admin", "domain": "admin_nav", "kind": "tkey", "tier": "core"},
            {"key": "k_ops", "default": "Ops", "domain": "admin_requests", "kind": "tkey", "tier": "core"},
        ],
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_domains",
        lambda: {"core_ops_domains": ["admin_requests"]},
    )

    db.session.add(UiTranslation(key="k_public", locale="de", text="Oeffentlich", is_active=True))
    db.session.add(UiTranslation(key="k_ops", locale="de", text="Betrieb", is_active=True))
    db.session.commit()

    resp = authenticated_admin_client.get("/admin/translations/coverage?format=json")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None

    assert payload["locales"] == ["fr", "en", "de", "bg"]
    assert payload["buckets"] == ["public", "volunteer", "admin", "ops"]
    assert "kpi" in payload
    assert "coverage" in payload
    assert "de" in payload["coverage"]
    assert "total" in payload["coverage"]["de"]

    de_total = payload["coverage"]["de"]["total"]
    assert isinstance(de_total["ratio"], float)
    assert isinstance(de_total["percent"], float)
    assert de_total["translated"] == 2
    assert de_total["total"] == 4
