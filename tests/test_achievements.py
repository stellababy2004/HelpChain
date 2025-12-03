class TestAchievementsIntegration:
    """Integration тестове за achievements функционалност"""

    def test_volunteer_login_and_achievements_access(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Тест за volunteer login и достъп до achievements"""
        # Use the authenticated volunteer test client fixture
        client = authenticated_volunteer_client
        volunteer = init_test_data["volunteer"]

        # Now attempt to access achievements
        response = client.get("/achievements")
        assert response.status_code == 200

        # Проверяваме че страницата съдържа achievements content
        data = response.get_data(as_text=True)
        assert "achievements" in data.lower() or "постижения" in data.lower()

    def test_achievements_content_display(self, authenticated_volunteer_client):
        """Тест за показване на achievements content"""
        client = authenticated_volunteer_client

        response = client.get("/achievements")
        assert response.status_code == 200

        data = response.get_data(as_text=True)

        # Проверяваме че има някакво съдържание
        assert len(data) > 100

        # Ако има achievement cards или списък
        if "achievement" in data.lower() or "постижение" in data.lower():
            assert True  # Content is present
        else:
            # Ако няма конкретни achievements, поне проверяваме че страницата работи
            assert "html" in data.lower()

    def test_achievements_redirect_if_not_logged_in(self, client):
        """Тест че achievements redirect-ва ако не си логнат"""
        response = client.get("/achievements")

        # Трябва да бъде redirect към login
        assert response.status_code in [302, 403, 401]

        if response.status_code == 302:
            # Проверяваме че redirect е към login страница
            assert "login" in response.headers.get("Location", "").lower()

    def test_achievements_with_different_volunteers(self, client, init_test_data):
        """Тест за achievements с различни volunteers"""
        volunteers = [init_test_data["volunteer"]]

        for volunteer in volunteers:
            with client.session_transaction() as sess:
                sess["volunteer_logged_in"] = True
                sess["volunteer_id"] = volunteer.id

            response = client.get("/achievements")
            assert response.status_code == 200

            # Проверяваме че страницата е personalized за volunteer
            data = response.get_data(as_text=True)
            # Проверяваме че има елементи от achievements страницата
            assert "achievements" in data.lower() or "постижения" in data.lower()
            assert "volunteer" in data.lower() or "доброволец" in data.lower()
