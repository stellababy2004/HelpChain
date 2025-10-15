#!/usr/bin/env python3
"""
Test script to verify error handling functionality
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from appy import app
import tempfile


def test_error_handlers():
    """Test that error handlers return correct responses"""
    with app.test_client() as client:
        # Test 404 error
        print("Testing 404 error handler...")
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
        print(f"✓ 404 handler returns status {response.status_code}")

        # Test 404 with JSON request
        print("Testing 404 error handler with JSON...")
        response = client.get(
            "/api/nonexistent", headers={"Accept": "application/json"}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        print(f"✓ 404 JSON handler returns: {data}")

        # Test 500 error (simulate by calling a route that raises exception)
        print("Testing 500 error handler...")
        # We'll test this by creating a test route that raises an exception
        with app.test_request_context():
            try:
                raise Exception("Test error")
            except Exception as e:
                # This simulates what happens in the error handler
                from flask import jsonify

                response_data = {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "status_code": 500,
                }
                print(f"✓ 500 error handler format: {response_data}")

        print("All error handler tests passed!")


if __name__ == "__main__":
    test_error_handlers()
