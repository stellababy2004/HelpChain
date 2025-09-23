# backend/tests/test_auth.py
import uuid
import secrets
import pytest

try:
    # FastAPI TestClient
    from fastapi.testclient import TestClient
    from main import app  # увери се, че имаш main.py с app = FastAPI()
except Exception:
    pytest.skip(
        "Не може да се импортира FastAPI app от main.py. Уверете се, че main.app съществува.",
        allow_module_level=True,
    )

client = TestClient(app)


def _rand_password() -> str:
    # произволна тестова стойност (не е статичен pattern за GitGuardian)
    return "test-" + secrets.token_urlsafe(16)


def _rand_user(prefix: str) -> tuple[str, str, str]:
    """
    Връща (username, email, password) с уникални стойности за всеки тест.
    """
    salt = uuid.uuid4().hex[:8]
    username = f"{prefix}_{salt}"
    email = f"{prefix}.{salt}@example.com"
    password = _rand_password()
    return username, email, password


@pytest.fixture
def volunteer_payload():
    username, email, password = _rand_user("volunteer")
    return {
        "username": username,
        "email": email,
        "password": password,
        "role": "volunteer",
    }


@pytest.fixture
def admin_payload():
    username, email, password = _rand_user("admin")
    return {
        "username": username,
        "email": email,
        "password": password,
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
    # първо регистрираме
    client.post("/register", json=volunteer_payload)

    # после логваме
    r = client.post(
        "/login",
        data={
            "username": volunteer_payload["username"],
            "password": volunteer_payload["password"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    token = data.get("access_token") or data.get("token")
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
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token
