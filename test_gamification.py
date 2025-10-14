import sys

sys.path.append("backend")
from appy import app, db
from models import Volunteer
from gamification_service import GamificationService

with app.app_context():
    volunteer = Volunteer.query.filter_by(email="ivan@example.com").first()
    if volunteer:
        print(f"Volunteer: {volunteer.name}")

        # Test gamification service
        achievements = GamificationService.get_achievement_progress(volunteer)
        leaderboard = GamificationService.get_leaderboard(limit=5)

        print(f"Achievements: {len(achievements)} items")
        print(f"Leaderboard: {len(leaderboard)} entries")

        # Print first achievement if any
        if achievements:
            first_achievement = achievements[0]
            print(f"First achievement: {first_achievement}")

        # Print leaderboard
        for i, entry in enumerate(leaderboard[:3], 1):
            print(f"Leaderboard #{i}: {entry['name']} - {entry['points']} points")
