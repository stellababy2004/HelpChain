import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_main_pages_load(client):
    # Add here the main routes you want to check
    urls = [
        "/",
        "/login",
        "/register",
        "/dashboard",
        "/volunteer_dashboard",
        "/admin_dashboard",
        "/notifications_dashboard",
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code in (200, 302), f"Failed to load {url}"


def test_i18n_markers_in_templates():
    import glob
    import os

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    html_files = glob.glob(os.path.join(template_dir, "**", "*.html"), recursive=True)
    assert html_files, "No HTML templates found!"
    for file in html_files:
        with open(file, encoding="utf-8") as f:
            content = f.read()
            assert "_('" in content or '_("' in content, f"No i18n marker in {file}"
