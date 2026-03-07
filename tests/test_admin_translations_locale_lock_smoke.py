from backend.models import UiLocaleLock, UiTranslation


def test_admin_translations_locale_lock_blocks_ops_write(authenticated_admin_client, monkeypatch):
    # Superadmin (default fixture role) locks locale.
    lock_resp = authenticated_admin_client.post(
        "/admin/translations/locale-lock",
        data={"locale": "de", "action": "lock", "format": "json"},
    )
    assert lock_resp.status_code == 200
    lock_payload = lock_resp.get_json()
    assert lock_payload is not None
    assert lock_payload["ok"] is True
    assert lock_payload["is_locked"] is True

    # Ops can no longer write while locale is locked.
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "ops",
    )
    upsert_blocked = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "submit_request", "locale": "de", "text": "Senden", "format": "json"},
    )
    assert upsert_blocked.status_code == 423
    blocked_payload = upsert_blocked.get_json()
    assert blocked_payload is not None
    assert blocked_payload["error"] == "locale_locked"

    # Superadmin unlocks locale.
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "superadmin",
    )
    unlock_resp = authenticated_admin_client.post(
        "/admin/translations/locale-lock",
        data={"locale": "de", "action": "unlock", "format": "json"},
    )
    assert unlock_resp.status_code == 200
    unlock_payload = unlock_resp.get_json()
    assert unlock_payload is not None
    assert unlock_payload["is_locked"] is False

    # Ops write works again after unlock.
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "ops",
    )
    upsert_ok = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "submit_request", "locale": "de", "text": "Senden"},
        follow_redirects=True,
    )
    assert upsert_ok.status_code == 200
    row = UiTranslation.query.filter_by(key="submit_request", locale="de").first()
    assert row is not None
    assert row.text == "Senden"


def test_admin_translations_locale_lock_is_superadmin_only(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "ops",
    )
    denied = authenticated_admin_client.post(
        "/admin/translations/locale-lock",
        data={"locale": "de", "action": "lock", "format": "json"},
    )
    assert denied.status_code == 403

    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._admin_role_value",
        lambda: "superadmin",
    )
    allowed = authenticated_admin_client.post(
        "/admin/translations/locale-lock",
        data={"locale": "de", "action": "lock", "note": "Locked for release", "format": "json"},
    )
    assert allowed.status_code == 200
    lock_row = UiLocaleLock.query.filter_by(locale="de").first()
    assert lock_row is not None
    assert lock_row.is_locked is True
    assert (lock_row.note or "") == "Locked for release"
