#!/usr/bin/env python3
"""
Test script to check if test routes are registered and working
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_routes():
    """Test the routes using Flask test client"""
    from appy import app

    with app.test_client() as client:
        print("Testing routes with Flask test client...")

        # Test the working /api route first
        print("\n1. Testing /api route:")
        response = client.get("/api")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.get_data(as_text=True)[:200]}...")

        # Test the test routes
        routes_to_test = [
            "/test/trigger-400",
            "/test/trigger-401",
            "/test/trigger-429",
            "/test/trigger-validation-error",
            "/test/trigger-database-error",
        ]

        for route in routes_to_test:
            print(f"\n2. Testing {route}:")
            try:
                response = client.get(route)
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.get_data(as_text=True)[:200]}...")
            except Exception as e:
                print(f"   Error: {e}")

        # Check URL map
        print("\n3. Checking Flask URL map:")
        with app.app_context():
            rules = list(app.url_map.iter_rules())
            test_rules = [rule for rule in rules if "test" in rule.rule]
            print(f"   Found {len(test_rules)} test routes:")
            for rule in test_rules:
                print(f"     {rule.rule} -> {rule.endpoint}")


if __name__ == "__main__":
    test_routes()
