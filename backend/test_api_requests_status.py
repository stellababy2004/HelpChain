import pytest
from flask import url_for

from models import Request


def test_api_requests_filter_status(authenticated_admin_client, db_session):
    # Arrange: add test requests
    req1 = Request(name="Test1", email="test1@example.com", status="pending")
    req2 = Request(name="Test2", email="test2@example.com", status="completed")
    db_session.add_all([req1, req2])
    db_session.commit()

    # Act: filter by status
    resp = authenticated_admin_client.get("/admin/api/requests?status=pending")
    data = resp.get_json()
    assert resp.status_code == 200
    assert any(r["status"] == "pending" for r in data["items"])
    assert all(r["status"] == "pending" for r in data["items"])


def test_update_status_sends_email(monkeypatch, authenticated_admin_client, db_session):
    # Arrange: add a test request
    req = Request(name="Test User", email="testuser@example.com", status="pending")
    db_session.add(req)
    db_session.commit()

    sent = {}
    def fake_send_notification_email(recipient, subject, template, context):
        sent["recipient"] = recipient
        sent["subject"] = subject
        sent["context"] = context
        return True

    monkeypatch.setattr(
        "mail_service.send_notification_email", fake_send_notification_email
    )

    # Act: update status
    resp = authenticated_admin_client.post(
        f"/admin/update_status/{req.id}",
        data={"status": "completed"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert sent["recipient"] == "testuser@example.com"
    assert "completed" in sent["subject"]
    assert sent["context"]["new_status"] == "completed"
