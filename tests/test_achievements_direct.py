class TestAchievementsDirect:
    """Тестове за achievements функционалност с директен достъп"""

    def test_achievements_page_access(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Тест за достъп до achievements страница"""
        client = authenticated_volunteer_client

        response = client.get("/achievements")
        assert response.status_code == 200

        # Проверяваме че страницата съдържа achievements content
        data = response.get_data(as_text=True)
        assert "achievements" in data.lower() or "постижения" in data.lower()

    def test_achievements_data_structure(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Тест за структурата на achievements данни"""
        client = authenticated_volunteer_client

        response = client.get("/achievements")
        assert response.status_code == 200

        # Това е HTML response, така че проверяваме за наличие на ключови елементи
        data = response.get_data(as_text=True)

        # Проверяваме че има някаква структура за achievements
        # Може да има таблица, списък или JSON data
        assert len(data) > 100  # Reasonable minimum length

    def test_achievements_with_volunteer_data(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Тест за achievements с реални volunteer данни"""
        client = authenticated_volunteer_client
        volunteer = init_test_data["volunteer"]

        response = client.get("/achievements")
        assert response.status_code == 200

        # Проверяваме че volunteer данните се използват
        data = response.get_data(as_text=True)

        # Ако volunteer има points, те трябва да се показват
        if hasattr(volunteer, "points") and volunteer.points > 0:
            assert str(volunteer.points) in data

    def test_achievements_unauthenticated_access(self, client):
        """Тест че achievements изискват authentication"""
        response = client.get("/achievements")

        # Трябва да бъде redirect към login или forbidden
        assert response.status_code in [302, 403, 401]
