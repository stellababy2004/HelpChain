def test_index_shows_brand(client):
    rv = client.get("/")
    text = rv.get_data(as_text=True)
    assert rv.status_code == 200
    assert "HelpChain" in text or "Добре дошли" in text


def test_register_and_login_flow(client, app):
    resp = client.post(
        "/register",
        data={
            "username": "pytester",
            "email": "pytest@example.com",
            "password": "Test12345",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp2 = client.post(
        "/login",
        data={"email": "pytest@example.com", "password": "Test12345"},
        follow_redirects=True,
    )
    text2 = resp2.get_data(as_text=True)
    assert resp2.status_code == 200
    assert ("Влязохте успешно" in text2) or ("Влязъл" in text2)


def test_invalid_login_shows_message(client):
    resp = client.post(
        "/login", data={"email": "no@one", "password": "bad"}, follow_redirects=True
    )
    text = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Грешен имейл или парола" in text
