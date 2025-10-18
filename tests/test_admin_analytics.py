#!/usr/bin/env python
"""
Test script for admin analytics functionality
"""


def test_admin_analytics(authenticated_admin_client):
    """Test admin analytics page access"""
    # Access analytics page
    response = authenticated_admin_client.get("/admin_analytics")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Check if charts are present
    content = response.get_data(as_text=True)
    assert "chart-container" in content, "Chart containers not found in HTML"
    assert "Chart.js" in content, "Chart.js library not found"
    assert "trendsData" in content, "Trends data script not found"
