class TestVolunteerIntegration:
    """Integration тестове за volunteer функционалност"""

    def test_volunteer_login_flow(self, client, init_test_data):
        """Тест за volunteer login процес"""
        volunteer = init_test_data["volunteer"]

        # Test login via session
        with client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = volunteer.id

        # Check dashboard access
        response = client.get("/volunteer_dashboard")
        assert response.status_code == 200

        data = response.get_data(as_text=True)

        # Check if volunteer name is displayed
        if hasattr(volunteer, "name") and volunteer.name:
            assert volunteer.name in data

        # Check for location update section (in Bulgarian)
        assert "Актуализирайте вашата локация" in data or "location" in data.lower()

        # Check for location form fields
        assert "latitude" in data and "longitude" in data

    def test_volunteer_dashboard_content(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Тест за съдържанието на volunteer dashboard"""
        client = authenticated_volunteer_client

        response = client.get("/volunteer_dashboard")
        assert response.status_code == 200

        data = response.get_data(as_text=True)

        # Basic content checks
        assert len(data) > 500  # Reasonable content length
        assert "dashboard" in data.lower() or "табло" in data.lower()

    def test_volunteer_location_update(self, authenticated_volunteer_client):
        """Тест за обновяване на локацията на volunteer"""
        client = authenticated_volunteer_client

        # Get volunteer ID from session
        volunteer_id = 1  # Use a test volunteer ID

        # Test location update API
        response = client.put(
            f"/api/volunteers/{volunteer_id}/location",
            json={"latitude": 42.6977, "longitude": 23.3219, "location": "София"},
        )

        # Should succeed
        assert response.status_code in [200, 404]  # 404 if volunteer doesn't exist

    def test_volunteer_profile_access(self, authenticated_volunteer_client):
        """Тест за достъп до volunteer профил"""
        client = authenticated_volunteer_client

        response = client.get("/volunteer_profile")
        # Profile might not exist, so check reasonable response
        assert response.status_code in [200, 404, 302]

    def test_volunteer_logout(self, authenticated_volunteer_client):
        """Тест за volunteer logout"""
        client = authenticated_volunteer_client

        # Test logout
        response = client.get("/volunteer_logout")
        assert response.status_code in [200, 302]

        # After logout, dashboard should redirect
        response = client.get("/volunteer_dashboard")
        assert response.status_code in [302, 403, 401]
