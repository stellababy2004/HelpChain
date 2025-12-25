import os
import sys

sys.path.insert(0, ".")

from flask import Flask

from backend import models
from backend.extensions import db

app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = r"sqlite:///C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\instance\volunteers.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    try:
        print("Testing AdminUser model...")
        admin_user = (
            db.session.query(models.AdminUser).filter_by(username="admin").first()
        )
        print(f"Admin user found: {admin_user}")
        if admin_user:
            print(f"Username: {admin_user.username}")
            print(f"Password hash: {admin_user.password_hash[:20]}...")
            print(f"Check password: {admin_user.check_password('Admin123')}")
        else:
            print("No admin user found")

        # Also check if table exists
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables in database: {tables}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
