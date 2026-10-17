def test_language_cookie_security_flags(client, app):
    app.config["SESSION_COOKIE_SECURE"] = True

    response = client.get("/lang/fr?next=/", base_url="https://helpchain.live", follow_redirects=False)

    assert response.status_code in (301, 302, 303, 307, 308)

    cookies = response.headers.getlist("Set-Cookie")
    language_cookie = next(
        cookie for cookie in cookies if cookie.startswith("hc_lang=")
    )

    assert "Secure" in language_cookie
    assert "HttpOnly" in language_cookie
    assert "SameSite=Lax" in language_cookie


def test_language_cookie_allows_local_http(client, app):
    app.config["SESSION_COOKIE_SECURE"] = False

    response = client.get(
        "/lang/fr?next=/",
        base_url="http://localhost",
        follow_redirects=False,
    )

    cookies = response.headers.getlist("Set-Cookie")
    language_cookie = next(
        cookie for cookie in cookies if cookie.startswith("hc_lang=")
    )

    assert "Secure" not in language_cookie
    assert "HttpOnly" in language_cookie
    assert "SameSite=Lax" in language_cookie
