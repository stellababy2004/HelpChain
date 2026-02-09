import pytest
from flask import json
from backend.helpchain_backend.src.app import create_app


@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_api_chat_basic(client):
    resp = client.post(
        "/api/chat", json={"message": "Здравей!", "context": "emergency"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "Здравей" in data["reply"]
    assert "emergency" in data["reply"]


def test_api_chat_no_context(client):
    resp = client.post("/api/chat", json={"message": "Тест"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "Тест" in data["reply"]
