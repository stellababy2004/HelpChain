#!/usr/bin/env python3
"""Test admin login end-to-end against local dev server.

Writes `admin_login_response.html` and prints status codes and basic diagnostics.
"""

import re
import sys
from pathlib import Path

try:
    import requests
except Exception:
    print("requests library required; please install with pip install requests")
    sys.exit(2)

BASE = "http://127.0.0.1:5000"
session = requests.Session()
out_dir = Path(__file__).resolve().parent


# Helper to extract CSRF token from HTML
def extract_csrf(html: str):
    # Try common hidden input names
    m = re.search(
        r"<input[^>]+name=[\"']csrf_token[\"'][^>]*value=[\"']([^\"']+)[\"']", html
    )
    if m:
        return m.group(1)
    m = re.search(
        r"<input[^>]+name=[\"']token[\"'][^>]*value=[\"']([^\"']+)[\"']", html
    )
    if m:
        return m.group(1)
    # Fallback: meta tag
    m = re.search(
        r"<meta[^>]+name=[\"']csrf-token[\"'][^>]*content=[\"']([^\"']+)[\"']", html
    )
    if m:
        return m.group(1)
    return None


def main():
    print("GET /admin/login")
    r = session.get(BASE + "/admin/login")
    print("GET status:", r.status_code)
    html = r.text
    (out_dir / "admin_login_get.html").write_text(html, encoding="utf-8")
    csrf = extract_csrf(html)
    print("Extracted csrf:", csrf)

    data = {
        "username": "admin",
        "password": "Admin12345!",
    }
    if csrf:
        data["csrf_token"] = csrf
    print("POST /admin/login (form)")
    r2 = session.post(BASE + "/admin/login", data=data, allow_redirects=False)
    print("POST status:", r2.status_code)
    # If redirect, follow
    if 300 <= r2.status_code < 400 and "Location" in r2.headers:
        loc = r2.headers["Location"]
        print("Redirect to:", loc)
        r3 = session.get(BASE + loc)
        print("Follow GET status:", r3.status_code)
        final_html = r3.text
        (out_dir / "admin_login_response.html").write_text(final_html, encoding="utf-8")
        print("Saved admin_login_response.html")
    else:
        # Save the POST response body
        (out_dir / "admin_login_response.html").write_text(r2.text, encoding="utf-8")
        final_html = r2.text
        print("Saved admin_login_response.html (no redirect)")

    # Now GET dashboard directly
    print("GET /admin_dashboard")
    rdash = session.get(BASE + "/admin_dashboard")
    print("Dashboard status:", rdash.status_code)
    (out_dir / "admin_dashboard_response.html").write_text(rdash.text, encoding="utf-8")

    # Basic heuristics: check if the login page still present
    if (
        "Вход" in final_html
        or "admin_login" in final_html
        or "login" in final_html.lower()
    ):
        print("POST appears to have returned login page (login likely failed)")
    else:
        print("POST did not return obvious login page; check saved HTML files")

    # Print session cookies
    print("Session cookies:")
    for c in session.cookies:
        print(f" - {c.name} = {c.value} (domain={c.domain} path={c.path})")


if __name__ == "__main__":
    main()
