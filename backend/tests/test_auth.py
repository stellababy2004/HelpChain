import pytest
from fastapi.testclient import TestClient

# опитваме директен импорт от main.py в backend
try:
    from main import app
except Exception:
    pytest.skip(
        "Не може да се импортира FastAPI app от main.py. Уверете се, че main.app съществува.",
        allow_module_level=True,
    )

client = TestClient(app)


@pytest.fixture
def volunteer_payload():
    return {
        "username": "volunteer1",
        "email": "vol1@example.com",
        "password": "Secret123!",
        "role": "volunteer",
    }


@pytest.fixture
def admin_payload():
    return {
        "username": "admin1",
        "email": "admin1@example.com",
        "password": "AdminPass123!",
        "role": "admin",
    }


def test_register_volunteer(volunteer_payload):
    r = client.post("/register", json=volunteer_payload)
    assert r.status_code in (200, 201)
    data = r.json()
    assert "id" in data or "email" in data


def test_register_admin(admin_payload):
    r = client.post("/register", json=admin_payload)
    assert r.status_code in (200, 201)
    data = r.json()
    assert "id" in data or "email" in data


def test_login_volunteer(volunteer_payload):
    client.post("/register", json=volunteer_payload)
    r = client.post(
        "/login",
        data={
            "username": volunteer_payload["username"],
            "password": volunteer_payload["password"],
        },
    )
    assert r.status_code == 200
    token = r.json().get("access_token") or r.json().get("token")
    assert token


def test_login_admin(admin_payload):
    client.post("/register", json=admin_payload)
    r = client.post(
        "/login",
        data={
            "username": admin_payload["username"],
            "password": admin_payload["password"],
        },
    )
    assert r.status_code == 200
    token = r.json().get("access_token") or r.json().get("token")
    assert token
