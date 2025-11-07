import pytest

from appy import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_signup_and_confirm(client):
    payload = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "TestPass123",
    }
    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    # In TESTING mode the endpoint returns the confirm_url so tests can follow it
    assert "confirm_url" in data

    confirm_url = data["confirm_url"]
    # Follow the confirmation URL
    cresp = client.get(confirm_url)
    assert cresp.status_code == 200
    cdata = cresp.get_json()
    assert cdata["success"] is True
