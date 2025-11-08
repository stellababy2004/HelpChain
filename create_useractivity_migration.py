#!/usr/bin/env python3
"""
Manual migration script to create UserActivity table
"""

import os
import sys

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__) + "\\backend")

# Import the app and models
from appy import app
from models import UserActivityTypeEnum


def create_migration():
    """Create the migration for UserActivity table"""
    with app.app_context():
        # Get the database
        db = app.extensions["migrate"].db

        # Create all tables (including UserActivity)
        print("Creating UserActivity table...")
        db.create_all()

        print("✅ UserActivity table created successfully!")
        print(
            "📊 Available activity types:", len([t.value for t in UserActivityTypeEnum])
        )
        print("🎯 Sample types:", [t.value for t in list(UserActivityTypeEnum)[:5]])


if __name__ == "__main__":
    create_migration()
