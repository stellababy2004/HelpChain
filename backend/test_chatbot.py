#!/usr/bin/env python3
"""
Тест на чатбот функционалността (с mocked HTTP повиквания)
"""
import os

import pytest
import requests

BASE_URL = os.getenv("HELPCHAIN_BASE_URL", "http://127.0.0.1:5000")


@pytest.fixture
def mock_requests(monkeypatch):
    class DummyResp:
        def __init__(self, status_code, json_data=None, text=""):
            self.status_code = status_code
            self._json = json_data or {}
            self.text = text

        def json(self):
            return self._json

    def fake_get(url, *args, **kwargs):
        if url.endswith("/chatbot/init"):
            return DummyResp(
                200,
                {
                    "session_id": "test-session",
                    "welcome_message": "Welcome to HelpChain",
                    "quick_questions": [],
                },
            )
        return DummyResp(404, {}, "not found")

    def fake_post(url, *args, **kwargs):
        if url.endswith("/chatbot/message"):
            payload = kwargs.get("json") or {}
            msg = payload.get("message", "")
            return DummyResp(
                200,
                {
                    "message": f"Echo: {msg}",
                    "type": "text",
                    "suggestions": [],
                },
            )
        return DummyResp(404, {}, "not found")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    yield


@pytest.fixture
def session_id(mock_requests):
    # инициализира "сесия" чрез mock (в реални тестове може да се подмени)
    from requests import get

    r = get(f"{BASE_URL}/chatbot/init")
    return r.json().get("session_id")


@pytest.mark.parametrize(
    "message",
    [
        "Hello, test message",
        "Как мога да се регистрирам?",
        "Невалиден въпрос за тест на fallback",
    ],
)
def test_chatbot_message(session_id, message):
    """Проверява, че изпращането на съобщение връща валиден отговор"""
    from requests import post

    response = post(
        f"{BASE_URL}/chatbot/message",
        json={"message": message, "session_id": session_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "message" in data and data["message"]
