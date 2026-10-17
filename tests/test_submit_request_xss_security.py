def test_submit_request_escapes_user_input_in_html_attributes(client):
    payload = 'Stella" autofocus onfocus="alert(1)'

    response = client.post(
        "/submit_request",
        data={
            "name": payload,
            "email": "",
            "phone": "",
            "category": "housing",
            "urgency": "normal",
            "title": payload,
            "description": "Demande de logement suffisamment detaillee.",
            "address_line": payload,
            "postcode": "75001",
            "city": payload,
            "country": "France",
            "privacy_consent": "1",
        },
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert payload not in html
    assert 'autofocus onfocus="alert(1)"' not in html
    assert (
        "&#34;" in html
        or "&#x22;" in html
        or "&#34" in html
    )
