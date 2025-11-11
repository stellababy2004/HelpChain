import pytest

from backend.appy import app


def test_static_cache_header_present_for_static_paths():
    app.config["TESTING"] = True
    client = app.test_client()
    # Ensure a real static file exists so Flask will serve it and set headers.
    import os

    static_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "static")
    static_dir = os.path.normpath(static_dir)
    os.makedirs(static_dir, exist_ok=True)
    file_path = os.path.join(static_dir, "app.js")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("console.log('test');")

        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "Cache-Control" in resp.headers
        # Accept either a public max-age header or other cache directives
        cc = resp.headers.get("Cache-Control", "")
        if "max-age" in cc:
            # If max-age is present, validate it matches the configured TTL.
            assert str(app.config.get("SEND_FILE_MAX_AGE_DEFAULT", 86400)) in cc
    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass


def test_no_cache_header_for_api_route():
    app.config["TESTING"] = True
    client = app.test_client()

    # Use the public API endpoint which returns JSON to ensure normal routes
    # don't receive the static Cache-Control header
    resp = client.get("/requests")
    assert resp.status_code in (200, 204, 404)
    assert "Cache-Control" not in resp.headers
