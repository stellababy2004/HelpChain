#!/usr/bin/env python3
"""
Check URL map with Flask running without SocketIO
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def check_url_map():
    """Check the Flask URL map"""
    from appy import app

    with app.app_context():
        print("Checking Flask URL map...")
        rules = list(app.url_map.iter_rules())
        print(f"Total rules: {len(rules)}")

        # Look for test routes
        test_rules = [rule for rule in rules if "test" in rule.rule.lower()]
        print(f"Test routes found: {len(test_rules)}")

        for rule in test_rules:
            print(f"  {rule.rule} -> {rule.endpoint}")

        # Check if our specific routes exist
        specific_routes = [
            "/test/trigger-400",
            "/test/trigger-401",
            "/test/trigger-429",
        ]
        for route in specific_routes:
            matching_rules = [rule for rule in rules if rule.rule == route]
            if matching_rules:
                print(f"✓ Route {route} is registered")
            else:
                print(f"✗ Route {route} is NOT registered")


if __name__ == "__main__":
    check_url_map()
