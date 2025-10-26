"""
Integration tests for volunteer achievements system
"""

import pytest


class TestAchievementsIntegration:
    """Integration tests for achievements functionality"""

    def test_volunteer_login_and_achievements_access(self, client, init_test_data):
        """Test that volunteer can login and access achievements page"""
        # Get test data
        volunteer = init_test_data["volunteer"]

        # First, login as volunteer
        login_data = {"email": volunteer.email}

        # Post to volunteer login
        response = client.post("/volunteer_login", data=login_data)
        assert response.status_code == 302  # Should redirect to verify code

        # Simulate code verification by setting session directly
        with client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = volunteer.id
            sess["volunteer_name"] = volunteer.name

        # Now access achievements page
        response = client.get("/achievements")
        assert response.status_code == 200

        # Check that achievements content is present
        response_text = response.get_data(as_text=True)
        assert (
            "achievements" in response_text.lower()
            or "постижения" in response_text.lower()
        )
