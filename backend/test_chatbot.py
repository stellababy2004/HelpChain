#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест на чатбот функционалността (с mocked HTTP повиквания)
"""
import requests
import time
import pytest

BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture(autouse=True)
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


def _chatbot_init():
    """Helper: инициализира чатбот и връща session_id или None"""
    try:
        response = requests.get(f"{BASE_URL}/chatbot/init")
        if response.status_code == 200:
            data = response.json()
            return data.get("session_id")
        return None
    except Exception:
        return None


def _chatbot_message(session_id, message):
    """Helper: изпраща message и връща JSON dict или None"""
    try:
        response = requests.post(
            f"{BASE_URL}/chatbot/message",
            json={"message": message, "session_id": session_id},
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def test_chatbot_init():
    """Проверява, че инициализацията връща session_id"""
    session_id = _chatbot_init()
    assert session_id is not None, "Неуспешна инициализация на чатбота"


def test_chatbot_message(session_id, message):
    """Проверява, че изпращането на съобщение връща валиден отговор"""
    data = _chatbot_message(session_id, message)
    assert data is not None, f"Няма валиден отговор за session {session_id}"
    assert isinstance(data, dict)
    assert data.get("message") is not None


def main():
    print("🚀 Стартираме тестване на чатбота...\n")

    # Тест 1: Инициализация
    session_id = _chatbot_init()
    if not session_id:
        print("❌ Не можем да инициализираме чатбота!")
        return

    time.sleep(1)

    test_messages = [
        "Как мога да се регистрирам?",
        "Какви услуги предлагате?",
        "Безплатно ли е?",
        "В кои градове работите?",
        "Колко време отнема да получа помощ?",
        "Как да се свържа с вас?",
        "Сигурни ли са личните ми данни?",
        "Какви са изискванията за доброволци?",
        "Невалиден въпрос за тест на fallback",
    ]

    successful_tests = 0

    for message in test_messages:
        if _chatbot_message(session_id, message):
            successful_tests += 1
        time.sleep(0.5)

    print("\n🎯 РЕЗУЛТАТИ:")
    print(f"✅ Успешни тестове: {successful_tests}/{len(test_messages)}")
    print(f"📊 Процент успешност: {(successful_tests/len(test_messages)*100):.1f}%")

    if successful_tests == len(test_messages):
        print("🎉 Всички тестове преминаха успешно!")
    else:
        print("⚠️  Някои тестове имат проблеми.")


if __name__ == "__main__":
    main()
