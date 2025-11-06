#!/usr/bin/env python3
"""Initialize gamification database"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend.appy import app
from backend.gamification_service import GamificationService
from backend.models import db


def init_db():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()

        print("Initializing achievements...")
        try:
            GamificationService.initialize_achievements()
            print("Achievements initialized successfully!")
        except Exception as e:
            print(f"Error initializing achievements: {e}")

        print("Database and achievements initialized successfully!")


if __name__ == "__main__":
    init_db()
