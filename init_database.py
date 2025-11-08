#!/usr/bin/env python3
"""
Initialize database with current models (SQLite compatible)
This bypasses the PostgreSQL-specific migrations and creates tables directly from models.
"""

import os
import sys

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app


def init_database():
    with app.app_context():
        print("Creating database tables from models...")

        # Import all models to ensure they're registered
        from models import (
            AdminUser,
        )

        try:
            from models_with_analytics import (
                AnalyticsEvent,
                PredictiveModel,
                SentimentAnalysis,
                Task,
            )
        except ImportError:
            print("Analytics models not available, skipping...")

        # Create all tables
        from extensions import db

        db.create_all()

        print("Database tables created successfully!")

        # Check if admin user exists, create if not
        admin = AdminUser.query.filter_by(username="admin").first()
        if not admin:
            print("Creating default admin user...")
            admin = AdminUser(
                username="admin", email="admin@helpchain.live", role="admin"
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created: admin/admin123")
        else:
            print("Admin user already exists")


if __name__ == "__main__":
    init_database()
