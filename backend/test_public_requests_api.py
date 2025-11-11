import json

import pytest

from appy import app, db
from backend.models import HelpRequest


def test_public_requests_list(client):
    # Добави тестова заявка
    req = HelpRequest(
        name="Тест",
        email="test@example.com",
        title="food",
        location_text="София",
        message="Нуждая се от храна",
        description="Нуждая се от храна",
        status="pending",
        city="София",
    )
    db.session.add(req)
    db.session.commit()

    # Тествай списъка
    resp = client.get("/requests")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(r["title"] == "food" for r in data)

    # Филтрирай по статус
    resp2 = client.get("/requests?status=pending")
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert any(r["status"] == "pending" for r in data2)

    # Търси по ключова дума
    resp3 = client.get("/requests?q=храна")
    assert resp3.status_code == 200
    data3 = resp3.get_json()
    assert any("храна" in r["description"] for r in data3)


def test_public_request_detail(client):
    req = HelpRequest(
        name="Детайл",
        email="detail@example.com",
        title="medicine",
        location_text="Пловдив",
        message="Нуждая се от лекарства",
        description="Нуждая се от лекарства",
        status="pending",
        city="Пловдив",
        phone="0888123456",
    )
    db.session.add(req)
    db.session.commit()

    resp = client.get(f"/request/{req.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["email"] == "detail@example.com"
    assert data["phone"] == "0888123456"
    assert data["title"] == "medicine"


def test_public_create_request(client):
    payload = {
        "name": "API User",
        "email": "api@example.com",
        "category": "other",
        "location": "Варна",
        "problem": "Тестова заявка чрез API",
    }
    resp = client.post(
        "/requests", data=json.dumps(payload), content_type="application/json"
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["request"]["title"] == "other"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            # Ensure session is removed and schema dropped
            try:
                db.session.remove()
            except Exception:
                pass
            db.drop_all()
            # Best-effort: dispose engine so DBAPI connections are closed
            try:
                db.engine.dispose()
            except Exception:
                pass
