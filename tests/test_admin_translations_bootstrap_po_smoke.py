from backend.models import UiTranslation


class _FakeTranslations:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    def gettext(self, msgid: str) -> str:
        return self._mapping.get(msgid, msgid)


def test_admin_translations_bootstrap_from_po_ops(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_key_registry",
        lambda: [
            {
                "key": "msgid:Next action",
                "default": "Next action",
                "domain": "admin_case",
                "kind": "msgid",
                "tier": "core",
            },
            {
                "key": "submit_request",
                "default": "Submit request",
                "domain": "buttons",
                "kind": "tkey",
                "tier": "core",
            },
        ],
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_domains",
        lambda: {"core_ops_domains": ["admin_case", "buttons"]},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_babel_translations",
        lambda _locale: _FakeTranslations({"Next action": "N\u00e4chste Aktion"}),
    )

    resp = authenticated_admin_client.post(
        "/admin/translations/bootstrap-from-po",
        data={"locale": "de", "view": "ops", "limit": "50", "format": "json"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["po_found_applied"] == 1
    assert payload["db_existing_skipped"] == 0

    row = UiTranslation.query.filter_by(locale="de", key="msgid:Next action").first()
    assert row is not None
    assert row.text == "N\u00e4chste Aktion"

    # t-key is intentionally ignored by PO bootstrap
    t_key_row = UiTranslation.query.filter_by(locale="de", key="submit_request").first()
    assert t_key_row is None


def test_admin_translations_bootstrap_from_po_does_not_overwrite(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_key_registry",
        lambda: [
            {
                "key": "msgid:Next action",
                "default": "Next action",
                "domain": "admin_case",
                "kind": "msgid",
                "tier": "core",
            }
        ],
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_ui_domains",
        lambda: {"core_ops_domains": ["admin_case"]},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._load_babel_translations",
        lambda _locale: _FakeTranslations({"Next action": "N\u00e4chste Aktion"}),
    )

    existing = UiTranslation(key="msgid:Next action", locale="de", text="Manual override")
    from backend.models import db

    db.session.add(existing)
    db.session.commit()

    resp = authenticated_admin_client.post(
        "/admin/translations/bootstrap-from-po",
        data={"locale": "de", "view": "ops", "limit": "50", "format": "json"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["po_found_applied"] == 0
    assert payload["db_existing_skipped"] == 1

    row = UiTranslation.query.filter_by(locale="de", key="msgid:Next action").first()
    assert row is not None
    assert row.text == "Manual override"
