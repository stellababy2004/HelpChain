from backend.models import UiTranslation


def test_only_missing_shows_registry_key_and_hides_after_override(authenticated_admin_client, session):
    key = "case_intelligence_next_action"
    locale = "de"

    # Ensure clean state for this key/locale.
    UiTranslation.query.filter_by(key=key, locale=locale).delete()
    session.commit()

    r1 = authenticated_admin_client.get(f"/admin/translations?locale={locale}&only_missing=1&view=all")
    assert r1.status_code == 200
    body1 = r1.get_data(as_text=True)
    assert key in body1

    session.add(UiTranslation(key=key, locale=locale, text="Nächste Aktion"))
    session.commit()

    r2 = authenticated_admin_client.get(f"/admin/translations?locale={locale}&only_missing=1&view=all")
    assert r2.status_code == 200
    body2 = r2.get_data(as_text=True)
    assert key not in body2
