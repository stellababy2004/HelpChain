from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy import text

from backend.helpchain_backend.src.app import create_app
from backend.models import Request, db


def test_app_boot():
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    assert app is not None
    with app.app_context():
        assert app.name


def test_database_connection(app, db_schema):
    with app.app_context():
        result = db.session.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_public_routes_health(client):
    expected_ok = {200, 301, 302, 303, 307, 308}
    for path in ("/", "/submit_request", "/faq", "/contact", "/legal", "/privacy", "/terms"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code in expected_ok, f"{path} returned {resp.status_code}"
        assert resp.status_code != 500, f"{path} returned 500"


def test_api_blueprint_routes_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/ai/status" in rules
    assert "/api/chatbot/message" in rules
    assert any(rule.endpoint.startswith("api.") for rule in app.url_map.iter_rules())


def test_admin_routes_health(client):
    # Admin may require auth; we only assert no server crash.
    for path in ("/admin", "/admin/requests"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code != 500, f"{path} returned 500"


def test_request_model_query(app, db_schema):
    with app.app_context():
        inspector = inspect(db.engine)
        assert "requests" in inspector.get_table_names()
        total = db.session.query(Request).count()
        assert isinstance(total, int)
