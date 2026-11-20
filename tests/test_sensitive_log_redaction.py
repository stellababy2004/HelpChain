"""Regression checks: sensitive SMS and provider error payloads must not enter logs."""

import logging

from flask import Flask

from backend import mail_service, sms_service


def test_disabled_sms_does_not_log_recipient_or_body(caplog):
    app = Flask(__name__)
    app.config["SMS_CONFIG"] = {"enabled": False}
    with app.app_context(), caplog.at_level(logging.INFO, logger=sms_service.logger.name):
        assert sms_service.send_notification_sms("+359899123456", "FIXTURE-SECRET-SMS") is True
    assert "+359899123456" not in caplog.text
    assert "FIXTURE-SECRET-SMS" not in caplog.text
    assert "message_length=" in caplog.text


def test_mock_sms_does_not_log_recipient_or_body(caplog, monkeypatch):
    monkeypatch.setattr(sms_service, "_send_mock_sms", sms_service._send_mock_sms)
    with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
        sms_service._send_mock_sms("+359899123456", "FIXTURE-SECRET-SMS")
    assert "+359899123456" not in caplog.text
    assert "FIXTURE-SECRET-SMS" not in caplog.text


def test_resend_http_error_redacts_response_body(monkeypatch, caplog):
    class Response:
        status_code = 422
        text = "FIXTURE-SECRET-PROVIDER-RESPONSE"

    monkeypatch.setenv("RESEND_API_KEY", "fixture-key")
    monkeypatch.setattr(mail_service.requests, "post", lambda *args, **kwargs: Response())
    app = Flask(__name__)
    with app.app_context(), caplog.at_level(logging.ERROR, logger=mail_service.logger.name):
        assert mail_service._send_via_resend(
            recipient="fixture@example.test",
            subject="fixture",
            html_content="fixture",
            text_content="fixture",
            from_name="HelpChain",
            mail_sender="sender@example.test",
            reply_to=None,
        ) is False
    assert "FIXTURE-SECRET-PROVIDER-RESPONSE" not in caplog.text
    assert "response_body_redacted=true" in caplog.text
