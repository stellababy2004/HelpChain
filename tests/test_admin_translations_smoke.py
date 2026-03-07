from backend.models import UiTranslation, db


def test_admin_translations_list_shows_db_override(authenticated_admin_client, session):
    row = UiTranslation(key="submit_request", locale="de", text="Anfrage senden")
    session.add(row)
    session.commit()

    resp = authenticated_admin_client.get("/admin/translations?locale=de&view=all")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "submit_request" in body
    assert "Anfrage senden" in body


def test_admin_translations_upsert_and_delete(authenticated_admin_client):
    upsert = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "volunteer_dashboard", "locale": "de", "text": "Freiwilligen-Dashboard"},
        follow_redirects=True,
    )
    assert upsert.status_code == 200

    created = UiTranslation.query.filter_by(key="volunteer_dashboard", locale="de").first()
    assert created is not None
    assert created.text == "Freiwilligen-Dashboard"

    delete = authenticated_admin_client.post(
        "/admin/translations/delete",
        data={"key": "volunteer_dashboard", "locale": "de"},
        follow_redirects=True,
    )
    assert delete.status_code == 200

    deleted = UiTranslation.query.filter_by(key="volunteer_dashboard", locale="de").first()
    assert deleted is None


def test_admin_translations_suggest_and_approve_flow(authenticated_admin_client):
    suggest = authenticated_admin_client.post(
        "/admin/translations/suggest",
        data={"key": "case_intelligence_next_action", "locale": "de"},
    )
    assert suggest.status_code == 200
    payload = suggest.get_json()
    assert payload is not None
    assert payload["key"] == "case_intelligence_next_action"
    assert payload["locale"] == "de"
    assert len(payload.get("suggestions") or []) == 3

    chosen = payload["suggestions"][0]["text"]
    save = authenticated_admin_client.post(
        "/admin/translations/upsert",
        data={"key": "case_intelligence_next_action", "locale": "de", "text": chosen},
        follow_redirects=True,
    )
    assert save.status_code == 200

    row = UiTranslation.query.filter_by(key="case_intelligence_next_action", locale="de").first()
    assert row is not None
    assert row.text == chosen
