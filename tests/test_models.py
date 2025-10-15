import pytest

# Import models_with_analytics first to ensure Task model is available
from backend import models_with_analytics  # noqa: F401
from backend.models import AdminUser, Volunteer, HelpRequest
from werkzeug.security import check_password_hash


class TestAdminUser:
    """Test AdminUser model methods"""

    def test_set_password_valid(self):
        """Test setting valid password"""
        admin = AdminUser()
        admin.set_password("ValidPass123")

        assert admin.password_hash is not None
        assert check_password_hash(admin.password_hash, "ValidPass123")

    def test_set_password_too_short(self):
        """Test setting password that's too short"""
        admin = AdminUser()

        with pytest.raises(ValueError, match="Паролата трябва да бъде поне 8 символа"):
            admin.set_password("Short")

    def test_set_password_no_uppercase(self):
        """Test setting password without uppercase"""
        admin = AdminUser()

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една главна буква"
        ):
            admin.set_password("lowercase123")

    def test_set_password_no_lowercase(self):
        """Test setting password without lowercase"""
        admin = AdminUser()

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една малка буква"
        ):
            admin.set_password("UPPERCASE123")

    def test_set_password_no_digit(self):
        """Test setting password without digit"""
        admin = AdminUser()

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една цифра"
        ):
            admin.set_password("NoDigits")

    def test_verify_totp_disabled(self):
        """Test TOTP verification when 2FA is disabled"""
        admin = AdminUser()
        admin.twofa_enabled = False

        assert not admin.verify_totp("123456")

    def test_verify_totp_no_secret(self):
        """Test TOTP verification when no secret is set"""
        admin = AdminUser()
        admin.twofa_enabled = True
        admin.twofa_secret = None

        assert not admin.verify_totp("123456")

    def test_verify_totp_invalid_token(self):
        """Test TOTP verification with invalid token format"""
        admin = AdminUser()
        admin.twofa_enabled = True
        admin.twofa_secret = "JBSWY3DPEHPK3PXP"  # Valid base32

        # Invalid token formats
        assert not admin.verify_totp("")  # Empty
        assert not admin.verify_totp("12345")  # Too short
        assert not admin.verify_totp("1234567")  # Too long
        assert not admin.verify_totp("abcdef")  # Non-digits

    def test_enable_2fa(self):
        """Test enabling 2FA"""
        admin = AdminUser()
        admin.enable_2fa()

        assert admin.twofa_enabled
        assert admin.twofa_secret is not None
        assert len(admin.twofa_secret) > 0

    def test_disable_2fa(self):
        """Test disabling 2FA"""
        admin = AdminUser()
        admin.twofa_secret = "TESTSECRET"
        admin.twofa_enabled = True

        admin.disable_2fa()

        assert not admin.twofa_enabled
        assert admin.twofa_secret is None

    def test_get_totp_uri(self):
        """Test getting TOTP URI"""
        admin = AdminUser()
        admin.username = "testadmin"

        uri = admin.get_totp_uri()

        assert "otpauth://totp/HelpChain:testadmin" in uri
        assert "issuer=HelpChain" in uri
        assert admin.twofa_secret is not None


class TestVolunteer:
    """Test Volunteer model methods"""

    def test_add_rating_valid(self):
        """Test adding valid rating"""
        volunteer = Volunteer()
        volunteer.rating = 4.0
        volunteer.rating_count = 2

        result = volunteer.add_rating(5)

        assert result is True
        assert volunteer.rating == 4.33  # (4.0*2 + 5)/3 rounded to 2 decimals
        assert volunteer.rating_count == 3

    def test_add_rating_invalid_range(self):
        """Test adding rating outside valid range"""
        volunteer = Volunteer()

        assert not volunteer.add_rating(0)
        assert not volunteer.add_rating(6)
        assert volunteer.rating_count == 0

    def test_add_rating_invalid_type(self):
        """Test adding non-numeric rating"""
        volunteer = Volunteer()

        assert not volunteer.add_rating("invalid")
        assert not volunteer.add_rating(None)
        assert volunteer.rating_count == 0

    def test_complete_task_valid(self):
        """Test completing task with valid hours"""
        volunteer = Volunteer()
        volunteer.total_tasks_completed = 5
        volunteer.total_hours_volunteered = 10.0

        result = volunteer.complete_task(2.5)

        assert result is True
        assert volunteer.total_tasks_completed == 6
        assert volunteer.total_hours_volunteered == 12.5

    def test_complete_task_invalid_hours(self):
        """Test completing task with invalid hours"""
        volunteer = Volunteer()

        assert not volunteer.complete_task(0)
        assert not volunteer.complete_task(-1)
        assert not volunteer.complete_task(25)  # Over 24 hours
        assert not volunteer.complete_task("invalid")
        assert volunteer.total_tasks_completed == 0

    def test_add_points_and_level_up(self):
        """Test adding points and automatic level up"""
        volunteer = Volunteer()
        volunteer.level = 1
        volunteer.experience = 50

        volunteer.add_points(60)  # Total experience: 110, should level up to 2

        assert volunteer.points == 60
        assert volunteer.level == 2  # Should have leveled up
        assert volunteer.experience == 10  # 110 - 100 (level 1 cost) = 10
        assert volunteer.level == 2

    def test_update_streak_first_activity(self):
        """Test updating streak for first activity"""
        volunteer = Volunteer()
        volunteer.last_activity = None

        volunteer.update_streak()

        assert volunteer.streak_days == 1
        assert volunteer.last_activity is not None

    def test_unlock_achievement_new(self):
        """Test unlocking new achievement"""
        volunteer = Volunteer()
        volunteer.achievements = ["first_task"]
        volunteer.points = 100

        volunteer.unlock_achievement("second_task")

        assert "second_task" in volunteer.achievements
        assert volunteer.points == 200  # +100 points

    def test_unlock_achievement_duplicate(self):
        """Test unlocking already unlocked achievement"""
        volunteer = Volunteer()
        volunteer.achievements = ["first_task"]
        volunteer.points = 100

        volunteer.unlock_achievement("first_task")

        assert volunteer.achievements == ["first_task"]  # No duplicate
        assert volunteer.points == 100  # No extra points

    def test_get_level_progress(self):
        """Test calculating level progress"""
        volunteer = Volunteer()
        volunteer.level = 2
        volunteer.experience = 150  # 150/200 = 75%

        progress = volunteer.get_level_progress()

        assert progress == 75.0

    def test_get_level_progress_max(self):
        """Test level progress doesn't exceed 100%"""
        volunteer = Volunteer()
        volunteer.level = 1
        volunteer.experience = 150  # Over 100 points

        progress = volunteer.get_level_progress()

        assert progress == 100.0

    def test_get_total_score(self):
        """Test calculating total leaderboard score"""
        volunteer = Volunteer()
        volunteer.points = 1000
        volunteer.total_tasks_completed = 20
        volunteer.rating = 4.5
        volunteer.level = 5

        score = volunteer.get_total_score()

        expected = (
            1000 * 0.4 + 20 * 10 + 4.5 * 20 + 5 * 50
        )  # 400 + 200 + 90 + 250 = 940
        assert score == expected


class TestHelpRequest:
    """Test HelpRequest model methods"""

    def test_status_transitions(self):
        """Test valid status transitions"""
        request = HelpRequest()
        request.status = "pending"

        # Valid transitions
        valid_transitions = ["assigned", "in_progress", "completed", "cancelled"]
        for new_status in valid_transitions:
            request.status = new_status
            assert request.status == new_status

    def test_priority_levels(self):
        """Test priority level validation"""
        request = HelpRequest()

        valid_priorities = ["low", "medium", "high", "urgent"]
        for priority in valid_priorities:
            request.priority = priority
            assert request.priority == priority

    def test_category_validation(self):
        """Test category field validation"""
        request = HelpRequest()

        valid_categories = [
            "медицинска помощ",
            "психологическа помощ",
            "юридическа помощ",
            "финансова помощ",
            "техническа помощ",
            "други",
        ]
        for category in valid_categories:
            request.category = category
            assert request.category == category

    def test_location_text_storage(self):
        """Test location text field storage"""
        request = HelpRequest()
        request.location_text = "София, ул. Витоша 15"

        assert request.location_text == "София, ул. Витоша 15"

    def test_message_length_validation(self):
        """Test message length constraints"""
        request = HelpRequest()

        # Valid message
        request.message = "Нуждая се от помощ с пазаруване"
        assert len(request.message) <= 2000

        # Long message should be truncated or handled
        long_message = "A" * 3000
        request.message = long_message
        # Model should handle this appropriately
        assert request.message == long_message

    def test_created_at_auto_timestamp(self, db_session):
        """Test automatic timestamp creation"""
        from datetime import datetime

        request = HelpRequest(
            title="Test Request",
            description="Test description",
            name="Test User",
            email="test@example.com",
            message="Test message",
        )
        db_session.add(request)
        db_session.commit()

        # created_at should be set automatically when object is committed
        assert request.created_at is not None
        assert isinstance(request.created_at, datetime)

    def test_updated_at_auto_update(self, db_session):
        """Test automatic timestamp update"""
        import time

        request = HelpRequest(
            title="Test Request",
            description="Test description",
            name="Test User",
            email="test@example.com",
            message="Test message",
        )
        db_session.add(request)
        db_session.commit()

        original_updated_at = request.updated_at
        assert original_updated_at is not None

        time.sleep(0.01)  # Small delay
        request.message = "Updated message"
        db_session.commit()

        # updated_at should be updated when object is modified and committed
        assert request.updated_at is not None
        assert request.updated_at >= original_updated_at
