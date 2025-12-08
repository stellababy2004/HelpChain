import sys

sys.path.append("backend")

from analytics_service import analytics_service
from flask import Flask

from backend.extensions import db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///C:/Users/Stella Barbarella/OneDrive/Documents/chatGPT/Projet BG/HelpChain/instance/volunteers.db"
db.init_app(app)

with app.app_context():
    try:
        dashboard_stats = analytics_service.get_dashboard_analytics(days=30)
        print("Analytics service response:")
        print(f"Type: {type(dashboard_stats)}")
        print(f"Keys: {list(dashboard_stats.keys()) if isinstance(dashboard_stats, dict) else 'Not a dict'}")

        if isinstance(dashboard_stats, dict):
            for key, value in dashboard_stats.items():
                print(f"{key}: {value}")
                if isinstance(value, dict) and "overview" in value:
                    print(f"  overview: {value['overview']}")
    except Exception as e:
        print(f"Error testing analytics service: {e}")
        import traceback

        traceback.print_exc()
