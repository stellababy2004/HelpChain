from io import BytesIO

from backend import mail_service


def test_legacy_chat_blueprint_is_not_registered(app):
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/chat/chat/upload" not in routes
    assert "/api/chat/chat/history/<room>" not in routes


def test_email_context_rejects_cross_tenant_and_internal_fields():
    for key in ("structure_id", "tenant_id", "request_id", "case_id", "description", "risk_level"):
        try:
            mail_service._validate_email_context("email_template.html", {key: "HC-CMPP-11-FOREIGN"})
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
    assert mail_service._validate_email_context("emails/magic_link.html", context) is context


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


def test_legacy_chat_upload_requires_authentication(client):
    response = client.post(
        "/api/chat/chat/upload",
        data={"file": (BytesIO(b"HC-CMPP-11-FILE"), "demo.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code in {302, 401, 403, 404}
