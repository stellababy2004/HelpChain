import pytest
from bs4 import BeautifulSoup

def test_emergency_requests_admin_access(authenticated_admin_client):
    resp = authenticated_admin_client.get("/admin/emergency-requests")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.data, "html.parser")
    assert soup.find("h1", string="Emergency requests")
    assert soup.find("table", class_="admin-table")


def test_emergency_requests_nonadmin_access(client):
    resp = client.get("/admin/emergency-requests", follow_redirects=True)
    # Should redirect or show error (403 or 200 with error message)
    assert resp.status_code in (200, 302, 403)
    # If 200, should show error message
    if resp.status_code == 200:
        text = resp.data.decode("utf-8", errors="ignore")
        assert ("Нямате достъп" in text) or ("login" in text.lower())
