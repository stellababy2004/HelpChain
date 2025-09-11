import json
import string
import random
import uuid
import time

# tests/test_additional.py

def test_register_without_follow_redirects(client):
    resp = client.post("/register", data={
        "username": "pytest_user",
        "email": "pytest_user@example.com",
        "password": "Test12345"
    }, follow_redirects=False)
    # should either create and redirect (302/303) or return 200
    assert resp.status_code in (200, 302, 303)

def test_login_without_follow_redirects(client):
    # attempt login (may redirect on success)
    resp = client.post("/login", data={
        "email": "pytest_user@example.com",
        "password": "Test12345"
    }, follow_redirects=False)
    assert resp.status_code in (200, 302, 303)

def test_ask_missing_message_returns_handled_response(client):
    resp = client.post("/ask", json={})
    # API should not result in 500; accept 200 or 400 and inspect payload if JSON
    assert resp.status_code in (200, 400)
    if resp.is_json:
        data = resp.get_json()
        assert isinstance(data, dict)
        # either provide an assistant answer or an error message
        assert "answer" in data or "error" in data

def test_ask_long_message(client):
    # tests/test_extra.py

    def unique_email():
        return f"pytest_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"

    def test_index_with_dummy_create_request_endpoint(client):
        # Add a temporary endpoint so url_for('create_request') in the template won't fail
        app = client.application
        if "create_request" not in app.view_functions:
            app.add_url_rule("/_test_create_request", "create_request", lambda: ("", 200))
        rv = client.get("/")
        assert rv.status_code == 200

    def test_public_pages_exist(client):
        for path in ("/privacy", "/terms", "/faq", "/success_stories"):
            resp = client.get(path)
            # accept 200 or 302 (if app redirects for some reason), but not 500
            assert resp.status_code in (200, 302, 303)

    def test_submit_request_get_and_post_no_500(client):
        # GET the submit page
        resp = client.get("/submit_request")
        assert resp.status_code in (200, 302, 303)
        # POST minimal form data; ensure no 500
        resp2 = client.post("/submit_request", data={"title": "Test", "description": "Help"}, follow_redirects=False)
        assert resp2.status_code != 500

    def test_register_login_logout_sequence(client):
        email = unique_email()
        # register
        r = client.post("/register", data={"username": "pyuser", "email": email, "password": "Test12345"}, follow_redirects=False)
        assert r.status_code in (200, 302, 303)
        # login
        r2 = client.post("/login", data={"email": email, "password": "Test12345"}, follow_redirects=False)
        assert r2.status_code in (200, 302, 303)
        # logout (if endpoint exists); accept many safe codes
        r3 = client.get("/logout", follow_redirects=False)
        assert r3.status_code in (200, 302, 303, 404)

    def test_admin_routes_protect_anonymous(client):
        # Admin dashboard should not be accessible anonymously (redirect to login or 401/403)
        resp = client.get("/admin_dashboard", follow_redirects=False)
        assert resp.status_code in (302, 401, 403, 404)

    def test_export_and_volunteers_endpoints_no_500(client):
        for path in ("/admin_volunteers", "/export_volunteers"):
            resp = client.get(path)
            assert resp.status_code != 500
            # acceptable statuses include 200, 302, 401, 403, 404
            assert resp.status_code in (200, 302, 303, 401, 403, 404)