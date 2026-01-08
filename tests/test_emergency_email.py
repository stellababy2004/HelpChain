

import pytest
from unittest.mock import patch

def make_emergency_request(client, **kwargs):
    data = dict(name="Test", phone="0888123456", email="test@x.bg", location="Sofia", category="emergency", problem="Test emergency situation", urgency="critical")
    data.update(kwargs)
    return client.post("/submit_request", data=data, follow_redirects=True)

def make_nonemergency_request(client, **kwargs):
    data = dict(name="Test", phone="0888123456", email="test@x.bg", location="Sofia", category="food", problem="Test food situation", urgency="normal")
    data.update(kwargs)
    return client.post("/submit_request", data=data, follow_redirects=True)


def test_emergency_email_sent_once(client, real_app):
    # Import models and db only after app fixture is created
    from flask import current_app
    from backend.models import Request
    from backend.extensions import db
    print("APP_ID", id(current_app._get_current_object()))
    print("DB_ID", id(db))
    print("EXT_DB_ID", id(current_app.extensions["sqlalchemy"].db))
    real_app.config["EMERGENCY_EMAIL_ENABLED"] = True
    real_app.config["EMERGENCY_EMAIL_COOLDOWN_SECONDS"] = 600
    # Ensure mail is present in extensions for testability
    if "mail" not in real_app.extensions:
        from backend.helpchain_backend.src import app as app_module
        real_app.extensions["mail"] = app_module.mail
    # Reset cooldown state before test
    real_app.extensions.setdefault("emergency_email_state", {})
    real_app.extensions["emergency_email_state"]["last_sent_ts"] = 0
    # Patch mail.send on the correct app instance
    with patch.object(real_app.extensions["mail"], "send", autospec=True) as mock_send:
        # First emergency triggers email
        data = dict(name="Test", phone="0888123456", email="test@x.bg", location="Sofia", category="emergency", problem="Test emergency situation", urgency="critical")
        resp1 = client.post("/submit_request", data=data, follow_redirects=True)
        assert resp1.status_code == 200
        mock_send.assert_called_once()
        # Second emergency (within cooldown) does NOT trigger
        resp2 = client.post("/submit_request", data=data, follow_redirects=True)
        assert resp2.status_code == 200
        assert mock_send.call_count == 1


def test_nonemergency_no_email(client, real_app):
    # Import models and db only after app fixture is created
    from flask import current_app
    from backend.models import Request
    from backend.extensions import db
    print("APP_ID", id(current_app._get_current_object()))
    print("DB_ID", id(db))
    print("EXT_DB_ID", id(current_app.extensions["sqlalchemy"].db))
    real_app.config["EMERGENCY_EMAIL_ENABLED"] = True
    real_app.config["EMERGENCY_EMAIL_COOLDOWN_SECONDS"] = 600
    if "mail" not in real_app.extensions:
        from backend.helpchain_backend.src import app as app_module
        real_app.extensions["mail"] = app_module.mail
    with patch.object(real_app.extensions["mail"], "send", autospec=True) as mock_send:
        resp = make_nonemergency_request(client)
        assert mock_send.call_count == 0
