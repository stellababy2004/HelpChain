"""Regression coverage for keeping administrative pages out of search indexes."""

import re


def test_admin_and_ops_responses_are_noindex(client):
    for path in ("/admin/login", "/admin/ops/login"):
        response = client.get(path)
        assert 200 <= response.status_code < 400, path
        assert response.headers.get("X-Robots-Tag") == "noindex, nofollow", path
        if response.status_code == 200:
            html = response.get_data(as_text=True)
            assert re.search(
                r'<meta[^>]+name="robots"[^>]+content="noindex,nofollow"', html
            ), path


def test_sitemap_contains_no_admin_or_ops_urls(client):
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    sitemap_text = sitemap.get_data(as_text=True).lower()
    assert "/admin" not in sitemap_text
    assert "/ops" not in sitemap_text
