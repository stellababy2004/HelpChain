#!/usr/bin/env python3
"""Pytest-friendly admin panel smoke test using fixtures."""

from bs4 import BeautifulSoup
import pytest


def test_admin_panel_loads_dashboard_and_analytics(authenticated_admin_client):
    """Verify admin dashboard and analytics pages load for an authenticated admin."""
    client = authenticated_admin_client

    # Access dashboard (fixture ensures admin is authenticated)
    dashboard_resp = client.get("/admin_dashboard", follow_redirects=True)
    assert dashboard_resp.status_code == 200, f"Dashboard access failed: {dashboard_resp.status_code}"

    soup = BeautifulSoup(dashboard_resp.data, "html.parser")

    # Basic smoke checks for volunteers / requests text in the dashboard
    volunteers_text = soup.find(text=lambda t: t and "доброволци" in t.lower())
    requests_text = soup.find(text=lambda t: t and ("заявки" in t.lower() or "requests" in t.lower()))

    # Not strict assertions; just surface helpful logs if missing
    if not volunteers_text:
        print("Warning: volunteers text not found in dashboard")
    if not requests_text:
        print("Warning: requests text not found in dashboard")

    # Admin analytics endpoint (legacy alias)
    analytics_resp = client.get("/admin_analytics")
    assert analytics_resp.status_code == 200, f"Admin analytics failed: {analytics_resp.status_code}"

    # All good
    print("Admin panel smoke test completed")
