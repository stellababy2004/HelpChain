import logging
import secrets
import sys
import types

from flask import Flask

from backend import sms_service

SMS_PHONE = "+359899123456"
SMS_MARKER = "FIXTURE-SECRET-SMS-CONTENT"


def _app(**sms_config):
    app = Flask(__name__)
    app.config["SMS_CONFIG"] = sms_config
    return app


def test_sms_disabled_logs_no_phone_or_message(caplog):
    with _app(enabled=False).app_context():
        with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
            assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is True

    assert SMS_MARKER not in caplog.text
    assert SMS_PHONE not in caplog.text
    assert "message_length=" in caplog.text


def test_twilio_failure_logs_only_error_type(monkeypatch, caplog):
    twilio = types.ModuleType("twilio")
    rest = types.ModuleType("twilio.rest")

    class FailingClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("FIXTURE-TWILIO-RESPONSE")

    rest.Client = FailingClient
    twilio.rest = rest
    monkeypatch.setitem(sys.modules, "twilio", twilio)
    monkeypatch.setitem(sys.modules, "twilio.rest", rest)

    config = {
        "enabled": True,
        "provider": "twilio",
        "twilio_account_sid": "fixture-sid",
        "twilio_auth_token": "fixture-token",
        "twilio_from_number": "+359888000000",
    }
    with _app(**config).app_context():
        with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
            assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is False

    assert "FIXTURE-TWILIO-RESPONSE" not in caplog.text
    assert SMS_PHONE not in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def test_twilio_success_does_not_log_provider_message_id(monkeypatch, caplog):
    twilio = types.ModuleType("twilio")
    rest = types.ModuleType("twilio.rest")

    class SuccessfulClient:
        def __init__(self, *args, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            return types.SimpleNamespace(sid="FIXTURE-TWILIO-MESSAGE-ID")

    rest.Client = SuccessfulClient
    twilio.rest = rest
    monkeypatch.setitem(sys.modules, "twilio", twilio)
    monkeypatch.setitem(sys.modules, "twilio.rest", rest)
    config = {
        "enabled": True,
        "provider": "twilio",
        "twilio_account_sid": "fixture-sid",
        "twilio_auth_token": "fixture-token",
        "twilio_from_number": "+359888000000",
    }

    with _app(**config).app_context():
        with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
            assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is True

    assert "FIXTURE-TWILIO-MESSAGE-ID" not in caplog.text
    assert SMS_MARKER not in caplog.text
    assert SMS_PHONE not in caplog.text


def test_nexmo_success_and_failure_do_not_log_payload(monkeypatch, caplog):
    class Response:
        def __init__(self, status):
            self.status = status

        def json(self):
            return {
                "messages": [{"status": self.status, "message-id": "FIXTURE-ID"}],
                "raw": "FIXTURE-NEXMO-RESPONSE",
            }

    monkeypatch.setattr(sms_service.requests, "post", lambda *a, **k: Response("0"))
    config = {
        "enabled": True,
        "provider": "nexmo",
        "nexmo_api_key": "fixture-key",
        "nexmo_api_secret": "fixture-secret",
    }
    with _app(**config).app_context():
        with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
            assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is True

    monkeypatch.setattr(sms_service.requests, "post", lambda *a, **k: Response("1"))
    with _app(**config).app_context():
        assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is False

    assert SMS_MARKER not in caplog.text
    assert SMS_PHONE not in caplog.text
    assert "FIXTURE-ID" not in caplog.text
    assert "FIXTURE-NEXMO-RESPONSE" not in caplog.text


def test_sms_outer_exception_logs_only_error_type(monkeypatch, caplog):
    monkeypatch.setattr(
        sms_service,
        "_clean_phone_number",
        lambda phone: (_ for _ in ()).throw(RuntimeError("FIXTURE-OUTER-SMS")),
    )
    with _app(enabled=True, provider="mock").app_context():
        with caplog.at_level(logging.INFO, logger=sms_service.logger.name):
            assert sms_service.send_notification_sms(SMS_PHONE, SMS_MARKER) is False

    assert "FIXTURE-OUTER-SMS" not in caplog.text
    assert SMS_PHONE not in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def _mail_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_urlsafe(32),
        MAIL_SERVER="smtp.fixture.test",
        MAIL_PORT=587,
        MAIL_USERNAME="fixture-user",
        MAIL_PASSWORD="fixture-password",
        MAIL_DEFAULT_SENDER="sender@fixture.test",
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_DEDUPE_MINUTES=0,
        MAIL_RL_MAX_SENT=100,
        FRONTEND_URL="https://fixture.test",
    )
    return app


def _patch_mail_common(monkeypatch, mail_service):
    monkeypatch.setattr(mail_service, "_send_via_resend", lambda **kwargs: False)
    monkeypatch.setattr(mail_service, "_recent_sent", lambda *a, **k: False)
    monkeypatch.setattr(mail_service, "_count_sent", lambda *a, **k: 0)
    monkeypatch.setattr(mail_service, "_log_email_event", lambda **kwargs: None)
    monkeypatch.setattr(
        mail_service,
        "render_template",
        lambda template, **context: "FIXTURE-SECRET-EMAIL-BODY",
    )


def test_email_fallback_redacts_body_and_markers(monkeypatch):
    from backend import mail_service

    output = []

    class FakeFile:
        def write(self, value):
            output.append(value)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FailingSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("FIXTURE-SMTP-RESPONSE")

    _patch_mail_common(monkeypatch, mail_service)
    monkeypatch.setattr("builtins.open", lambda *a, **k: FakeFile())
    monkeypatch.setattr(mail_service.smtplib, "SMTP", FailingSMTP)

    with _mail_app().app_context():
        assert (
            mail_service.send_notification_email(
                "fixture-recipient@example.test",
                "FIXTURE-SUBJECT-MARKER",
                "emails/magic_link.html",
                {"magic_link_url": "https://fixture.test/magic"},
                purpose="FIXTURE-SENSITIVE-PURPOSE-MARKER",
                structure_id=1,
            )
            is False
        )

    written = "".join(output)
    assert "FIXTURE-SECRET-EMAIL-BODY" not in written
    assert "fixture-recipient@example.test" not in written
    assert "FIXTURE-SUBJECT-MARKER" not in written
    assert "FIXTURE-SENSITIVE-PURPOSE-MARKER" not in written
    assert "purpose=generic" in written
    assert "Email body redacted" in written


def test_smtp_success_analytics_context_is_minimal(monkeypatch):
    from backend import mail_service

    events = []

    class SuccessfulSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            return None

        def login(self, *args):
            return None

        def send_message(self, message):
            return None

    class Analytics:
        def track_event(self, **kwargs):
            events.append(kwargs)

    _patch_mail_common(monkeypatch, mail_service)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", SuccessfulSMTP)
    monkeypatch.setattr(mail_service, "analytics_available", True)
    monkeypatch.setattr(mail_service, "analytics_service", Analytics())

    with _mail_app().app_context():
        assert (
            mail_service.send_notification_email(
                "fixture-recipient@example.test",
                "FIXTURE-SUBJECT-MARKER",
                "emails/magic_link.html",
                {"magic_link_url": "https://fixture.test/magic"},
                purpose="fixture",
                structure_id=1,
            )
            is True
        )

    context = events[0]["context"]
    assert "recipient" not in context
    assert "subject" not in context
    assert "message_id" not in context
    assert context["recipient_present"] is True
    assert context["subject_length"] == len("FIXTURE-SUBJECT-MARKER")


def test_smtp_auth_failure_and_resend_error_redact_exception(monkeypatch, caplog):
    from backend import mail_service

    class AuthFailSMTP:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            return None

        def login(self, *args):
            raise mail_service.smtplib.SMTPAuthenticationError(
                535, b"FIXTURE-SMTP-AUTH-RESPONSE"
            )

        def send_message(self, message):
            raise AssertionError("send_message should not be reached")

    _patch_mail_common(monkeypatch, mail_service)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", AuthFailSMTP)

    with _mail_app().app_context():
        with caplog.at_level(logging.INFO, logger=mail_service.logger.name):
            assert (
                mail_service.send_notification_email(
                    "fixture@example.test",
                    "Fixture subject",
                    "emails/magic_link.html",
                    {"magic_link_url": "https://fixture.test/magic"},
                    purpose="fixture",
                    structure_id=1,
                )
                is False
            )

    assert "FIXTURE-SMTP-AUTH-RESPONSE" not in caplog.text

    monkeypatch.setenv("RESEND_API_KEY", "fixture-resend-token")
    monkeypatch.setattr(
        mail_service.requests,
        "post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("FIXTURE-RESEND-ERROR")),
    )
    with _mail_app().app_context():
        assert (
            mail_service._send_via_resend(
                recipient="fixture@example.test",
                subject="FIXTURE-SUBJECT",
                html_content="FIXTURE-BODY",
                text_content="FIXTURE-TEXT",
                from_name="HelpChain",
                mail_sender="sender@fixture.test",
                reply_to=None,
            )
            is False
        )

    assert "FIXTURE-RESEND-ERROR" not in caplog.text

    monkeypatch.setattr(
        mail_service,
        "_recent_sent",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("FIXTURE-QUEUE-ERROR")),
    )
    with _mail_app().app_context():
        assert (
            mail_service.send_notification_email(
                "fixture@example.test",
                "Fixture subject",
                "emails/magic_link.html",
                {"magic_link_url": "https://fixture.test/magic"},
                purpose="fixture",
                structure_id=1,
            )
            is False
        )

    assert "FIXTURE-QUEUE-ERROR" not in caplog.text
