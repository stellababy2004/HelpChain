import logging
from io import BytesIO

from backend import mail_service


def test_legacy_chat_blueprint_is_not_registered(app):
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/chat/chat/upload" not in routes
    assert "/api/chat/chat/history/<room>" not in routes


def test_email_context_rejects_cross_tenant_and_internal_fields():
    for key in (
        "structure_id",
        "tenant_id",
        "request_id",
        "case_id",
        "description",
        "risk_level",
    ):
        try:
            mail_service._validate_email_context(
                "email_template.html", {key: "HC-CMPP-11-FOREIGN"}
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"context key was not rejected: {key}")


def test_email_context_rejects_nested_internal_fields():
    try:
        mail_service._validate_email_context(
            "email_template.html", {"task": {"description": "HC-CMPP-11-FOREIGN"}}
        )
    except ValueError:
        pass
    else:
        raise AssertionError("nested sensitive context was not rejected")


def test_email_context_keeps_legitimate_magic_link_fields():
    context = {
        "magic_link_url": "https://example.test/magic/demo",
        "ttl_minutes": 15,
        "ignore_line": "Ignorez ce message.",
    }
    assert (
        mail_service._validate_email_context("emails/magic_link.html", context)
        is context
    )


def test_email_context_rejects_unknown_template_and_keys():
    for template, context in (
        ("emails/not-real.html", {}),
        ("emails/magic_link.html", {"foreign_marker": "HC-CMPP-12"}),
    ):
        try:
            mail_service._validate_email_context(template, context)
        except ValueError:
            pass
        else:
            raise AssertionError("uncontracted email input was accepted")


def test_legacy_chat_upload_is_fail_closed_for_unauthenticated_callers(client):
    response = client.post(
        "/api/chat/chat/upload",
        data={"file": (BytesIO(b"HC-CMPP-11-FILE"), "demo.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 404


def test_demo_notification_failure_log_redacts_form_values(
    app, client, caplog, monkeypatch
):
    from backend.helpchain_backend.src.routes import main as main_routes

    fake_name = "HC-DEMO-LOG-NAME"
    fake_email = "hc-demo-log@example.test"
    fake_organisation = "HC-DEMO-LOG-ORGANISATION"
    fake_phone = "+35970070123"

    monkeypatch.setattr(main_routes, "_verify_turnstile_token", lambda **_: True)
    monkeypatch.setattr(mail_service, "send_notification_email", lambda **_: False)
    monkeypatch.setattr(main_routes.mail, "send", lambda *_args, **_kwargs: None)
    caplog.set_level(logging.WARNING)

    response = client.post(
        "/demo",
        data={
            "full_name": fake_name,
            "email": fake_email,
            "organisation": fake_organisation,
            "phone": fake_phone,
            "structure_type": "association",
            "organization_size": "small",
            "fonction": "test-role",
            "message": "Local-only demo notification test.",
        },
    )

    assert response.status_code == 303
    failure_logs = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.getMessage().startswith("Demo notification failed | lead_id=")
    ]
    assert len(failure_logs) == 1
    failure_log = failure_logs[0]
    assert "context_present=True" in failure_log
    for value in (fake_name, fake_email, fake_organisation, fake_phone):
        assert value not in failure_log
