import sys

# Add backend to path
sys.path.insert(
    0,
    r"c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend",
)

# Import app
from appy import app

with app.app_context():
    # Get all routes
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(
            {"endpoint": rule.endpoint, "methods": list(rule.methods), "url": str(rule)}
        )

    # Filter admin routes
    admin_routes = [
        r for r in routes if "admin" in r["endpoint"] or "admin" in r["url"]
    ]

    print("Admin routes:")
    for route in admin_routes:
        print(f"  {route['methods']} {route['url']} -> {route['endpoint']}")

    # Check if admin_analytics exists
    analytics_routes = [
        r for r in routes if "analytics" in r["endpoint"] or "analytics" in r["url"]
    ]
    print("\nAnalytics routes:")
    for route in analytics_routes:
        print(f"  {route['methods']} {route['url']} -> {route['endpoint']}")
