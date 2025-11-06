def test_index_route(client):
    # Debug: print all registered routes in the app
    print("\n=== ROUTES IN TEST FLASK APP ===")
    for rule in client.application.url_map.iter_rules():
        print(f"{rule.rule:30}  [{','.join(sorted(rule.methods))}]  -> {rule.endpoint}")
    print("=== END ROUTES ===\n")
    response = client.get("/")
    # Ако app е правилният, трябва да върне 200 или поне не 404
    assert response.status_code != 404
import pytest
from appy import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_public_requests_list(client):
    # Тест за GET /requests (публичен списък)
    response = client.get("/requests")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list) or isinstance(data, dict)


def test_public_request_detail_not_found(client):
    # Тест за GET /request/<id> с невалидно id
    response = client.get("/request/999999")
    assert response.status_code in (404, 400)


def test_public_create_request_invalid(client):
    # Тест за POST /requests с невалидни данни
    response = client.post("/requests", json={"name": "", "email": "bad", "problem": "short"})
    assert response.status_code == 400
    data = response.get_json()
    assert not data["success"]
    assert "errors" in data


def test_public_create_request_valid(client):
    # Тест за POST /requests с валидни данни
    payload = {
        "name": "Тест Потребител",
        "email": "test@example.com",
        "category": "Храна",
        "location": "София",
        "problem": "Нуждая се от помощ с пазаруване.",
        "phone": "0888123456",
        "city": "София"
    }
    response = client.post("/requests", json=payload)
    assert response.status_code in (200, 201)
    data = response.get_json()
    assert data["success"]
    assert "id" in data or "request" in data
