import json

import pytest

from ai_api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    # Проверяваме дали health endpoint е регистриран
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/api/health" in routes, f"/api/health not found in routes: {routes}"
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["qa_model_loaded"] is True
    assert "translation_models" in data


def test_ask(client):
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/api/ask" in routes, f"/api/ask not found in routes: {routes}"
    payload = {
        "question": "Кой е столицата на България?",
        "context": "Столицата на България е София.",
    }
    resp = client.post(
        "/api/ask", data=json.dumps(payload), content_type="application/json"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "answer" in data
    assert isinstance(data["answer"], str)


def test_translate(client):
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/api/translate" in routes, f"/api/translate not found in routes: {routes}"
    payload = {"text": "Здравей свят!", "src_lang": "bg", "tgt_lang": "en"}
    resp = client.post(
        "/api/translate", data=json.dumps(payload), content_type="application/json"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "translated" in data
    assert isinstance(data["translated"], str)


def test_detect_language(client):
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    assert (
        "/api/detect_language" in routes
    ), f"/api/detect_language not found in routes: {routes}"
    payload = {"text": "Bonjour le monde!"}
    resp = client.post(
        "/api/detect_language",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "language" in data
    assert isinstance(data["language"], str)
