import pytest
from backend.gamification_service import GamificationService
from backend.models import Achievement


class TestGamificationService:
    """Тестове за gamification service"""

    def test_get_achievement_progress(self, init_test_data, db_session):
        """Тест за получаване на achievement progress"""
        volunteer = init_test_data["volunteer"]

        # Get first achievement from database
        achievement = Achievement.query.first()
        if achievement:
            progress = GamificationService.get_achievement_progress(
                volunteer, achievement
            )
            assert isinstance(progress, (int, float))
            assert 0 <= progress <= 100
        else:
            # If no achievements exist, skip test
            pytest.skip("No achievements found in database")

    def test_get_leaderboard(self, init_test_data):
        """Тест за leaderboard функционалност"""
        leaderboard = GamificationService.get_leaderboard(limit=5)

        assert isinstance(leaderboard, list)
        assert len(leaderboard) <= 5

        # Ако има entries в leaderboard
        if leaderboard:
            entry = leaderboard[0]
            # Leaderboard returns Volunteer objects
            assert hasattr(entry, "name")  # Volunteer has name attribute
            assert hasattr(entry, "points")  # Volunteer has points attribute

    def test_achievement_unlocking(self, init_test_data):
        """Тест за unlocking achievements"""
        volunteer = init_test_data["volunteer"]

        # Test different scenarios
        # Това зависи от конкретната имплементация на gamification

        # За сега само проверяваме че функцията не хвърля exception
        try:
            unlocked = GamificationService.check_achievements(volunteer)
            assert isinstance(unlocked, list)
        except Exception as e:
            pytest.fail(f"Gamification service failed: {e}")

    def test_points_calculation(self, init_test_data):
        """Тест за points calculation"""
        volunteer = init_test_data["volunteer"]

        # Test basic points calculation
        # Това зависи от конкретната логика

        # За сега проверяваме че volunteer има points attribute
        assert hasattr(volunteer, "points")
        assert isinstance(volunteer.points, int)
        assert volunteer.points >= 0
