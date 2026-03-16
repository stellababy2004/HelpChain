from __future__ import annotations


def test_admin_volunteers_page_smoke(authenticated_admin_client):
    resp = authenticated_admin_client.get("/admin/volunteers", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert ("intervenant" in html.lower()) or ("volunteer" in html.lower())
    assert "traceback" not in html.lower()
