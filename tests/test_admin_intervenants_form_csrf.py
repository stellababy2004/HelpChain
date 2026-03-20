import re


def _csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert m, "CSRF token not found"
    return m.group(1)


def test_admin_intervenants_new_renders_csrf_field(authenticated_admin_client):
    authenticated_admin_client.application.config["WTF_CSRF_ENABLED"] = True

    resp = authenticated_admin_client.get("/admin/intervenants/new")
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert 'name="csrf_token"' in html
    assert _csrf(html)


def test_admin_intervenants_new_post_accepts_valid_csrf(authenticated_admin_client, session):
    authenticated_admin_client.application.config["WTF_CSRF_ENABLED"] = True

    page = authenticated_admin_client.get("/admin/intervenants/new")
    assert page.status_code == 200
    token = _csrf(page.get_data(as_text=True))

    payload = {
        "csrf_token": token,
        "full_name": "CSRF Intervenant",
        "email": "csrf-intervenant@test.local",
        "phone": "+33123456789",
        "profession": "doctor",
        "city": "Paris",
        "address": "10 Rue Test",
        "availability": "available",
        "latitude": "",
        "longitude": "",
        "structure_id": "",
    }

    resp = authenticated_admin_client.post(
        "/admin/intervenants/new",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)
    assert resp.status_code != 400
