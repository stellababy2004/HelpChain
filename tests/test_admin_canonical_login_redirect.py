def test_protected_admin_route_redirects_to_canonical_login(client):
    response = client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code in (302, 303)
    location = response.headers.get("Location", "")
    assert "/admin/login" in location
