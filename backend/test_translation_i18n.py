import pytest
from flask import Flask
from appy import app as flask_app


# Проверяваме преведения заглавен текст на страницата
@pytest.mark.parametrize(
    "lang,expected_text",
    [
        ("bg", "HelpChain – Свързваме хората, които помагат"),
        ("fr", "HelpChain – Nous connectons les personnes qui aident"),
        (
            "en",
            "HelpChain – Свързваме хората, които помагат",
        ),  # English не е преведен, остава българския текст
    ],
)
def test_home_translation(lang, expected_text):
    tester = flask_app.test_client()
    tester.get(f"/set_language/{lang}")
    response = tester.get("/")
    assert response.status_code == 200
    assert expected_text in response.data.decode("utf-8")
