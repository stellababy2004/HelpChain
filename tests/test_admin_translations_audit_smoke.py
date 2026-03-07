from backend.models import UiTranslationEvent


def test_admin_translations_audit_created_updated_deleted(authenticated_admin_client):
    created_resp = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "submit_request", "locale": "de", "text": "Anfrage senden"},
        follow_redirects=True,
    )
    assert created_resp.status_code == 200

    created_ev = (
        UiTranslationEvent.query.filter_by(locale="de", key="submit_request", action="created")
        .order_by(UiTranslationEvent.created_at.desc())
        .first()
    )
    assert created_ev is not None
    assert created_ev.source == "human"
    assert created_ev.old_text is None
    assert created_ev.new_text == "Anfrage senden"

    updated_resp = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "submit_request", "locale": "de", "text": "Neue Anfrage senden"},
        follow_redirects=True,
    )
    assert updated_resp.status_code == 200

    updated_ev = (
        UiTranslationEvent.query.filter_by(locale="de", key="submit_request", action="updated")
        .order_by(UiTranslationEvent.created_at.desc())
        .first()
    )
    assert updated_ev is not None
    assert updated_ev.source == "human"
    assert updated_ev.old_text == "Anfrage senden"
    assert updated_ev.new_text == "Neue Anfrage senden"

    deleted_resp = authenticated_admin_client.post(
        "/admin/translations/delete",
        data={"key": "submit_request", "locale": "de"},
        follow_redirects=True,
    )
    assert deleted_resp.status_code == 200

    deleted_ev = (
        UiTranslationEvent.query.filter_by(locale="de", key="submit_request", action="deleted")
        .order_by(UiTranslationEvent.created_at.desc())
        .first()
    )
    assert deleted_ev is not None
    assert deleted_ev.source == "human"
    assert deleted_ev.old_text == "Neue Anfrage senden"
    assert deleted_ev.new_text is None
