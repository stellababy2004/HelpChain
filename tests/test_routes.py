class TestRoutes:
    """Тестове за основните Flask routes"""

    def test_index_route(self, client):
        """Тест за началната страница"""
        response = client.get("/")

        assert response.status_code == 200
        # Проверяваме че страницата съдържа основни елементи
        assert b"HelpChain" in response.data or b"index" in response.data

    def test_privacy_route(self, client):
        """Тест за privacy страницата"""
        response = client.get("/privacy")

        assert response.status_code == 200
        assert b"privacy" in response.data or b"Privacy" in response.data

    def test_terms_route(self, client):
        """Тест за terms страницата"""
        response = client.get("/terms")

        assert response.status_code == 200
        assert b"terms" in response.data or b"Terms" in response.data

    def test_admin_login_get(self, client):
        """Тест за admin login страница (GET)"""
        response = client.get("/admin_login")

        assert response.status_code == 200
        assert (
            b"\xd0\x92\xd1\x85\xd0\xbe\xd0\xb4 \xd0\xb7\xd0\xb0 \xd0\xb0\xd0\xb4\xd0\xbc\xd0\xb8\xd0\xbd\xd0\xb8\xd1\x81\xd1\x82\xd1\x80\xd0\xb0\xd1\x82\xd0\xbe\xd1\x80"
            in response.data
        )  # Bulgarian for "Admin Login"

    def test_admin_login_post_invalid_credentials(self, client):
        """Тест за admin login с невалидни данни"""
        response = client.post(
            "/admin_login",
            data={"username": "wrong", "password": "wrong"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Трябва да остане на login страницата или да покаже грешка

    def test_volunteer_register_get(self, client):
        """Тест за volunteer register страница"""
        response = client.get("/volunteer_register")

        assert response.status_code == 200
        assert b"register" in response.data or b"volunteer" in response.data

    def test_volunteer_register_post_valid_data(self, client, db_session, mock_smtp):
        """Тест за volunteer register с валидни данни"""
        response = client.post(
            "/volunteer_register",
            data={
                "name": "Test Volunteer",
                "email": "test@example.com",
                "phone": "+359888123456",
                "location": "София",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Проверяваме че доброволецът е създаден в базата
        from backend.models import Volunteer

        volunteer = (
            db_session.query(Volunteer).filter_by(email="test@example.com").first()
        )
        assert volunteer is not None
        assert volunteer.name == "Test Volunteer"

    def test_volunteer_register_post_duplicate_email(self, client, test_volunteer):
        """Тест за volunteer register с дублиран email"""
        response = client.post(
            "/volunteer_register",
            data={
                "name": "Друг Доброволец",
                "email": test_volunteer.email,  # Същият email
                "phone": "+359888654321",
                "location": "Пловдив",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Трябва да покаже грешка за дублиран email

    def test_volunteer_login_get(self, client):
        """Тест за volunteer login страница"""
        response = client.get("/volunteer_login")

        assert response.status_code == 200
        assert b"login" in response.data or b"volunteer" in response.data

    def test_submit_request_get(self, client):
        """Тест за submit request страница"""
        response = client.get("/submit_request")

        assert response.status_code == 200
        assert b"submit" in response.data or b"request" in response.data

    def test_submit_request_post_valid_data(self, client, db_session, mock_smtp):
        """Тест за submit request с валидни данни"""
        response = client.post(
            "/submit_request",
            data={
                "name": "Тестов Потребител",
                "email": "user@example.com",
                "category": "Техническа помощ",
                "location": "София",
                "problem": "Имам нужда от помощ с компютър",
                "captcha": "7G5K",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Проверяваме че заявката е създадена
        from backend.models import HelpRequest

        request = (
            db_session.query(HelpRequest).filter_by(email="user@example.com").first()
        )
        assert request is not None
        assert request.name == "Тестов Потребител"

    def test_submit_request_post_invalid_captcha(self, client):
        """Тест за submit request с грешен captcha"""
        response = client.post(
            "/submit_request",
            data={
                "name": "Тестов Потребител",
                "email": "user@example.com",
                "category": "Техническа помощ",
                "location": "София",
                "problem": "Имам нужда от помощ",
                "captcha": "wrong",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Трябва да остане на формата с грешка

    def test_chatbot_route(self, client):
        """Тест за chatbot страницата"""
        response = client.get("/chatbot")

        assert response.status_code == 200
        assert b"chatbot" in response.data or b"chat" in response.data


class TestAPIRoutes:
    """Тестове за API routes"""

    def test_ai_status_api(self, client, mock_ai_service):
        """Тест за AI status API"""
        response = client.get("/api/ai/status")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)

    def test_chatbot_message_api_valid(self, client, mock_ai_service):
        """Тест за chatbot message API с валидни данни"""
        response = client.post(
            "/api/chatbot/message",
            json={"message": "Здравей", "session_id": "test_session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "response" in data
        assert "confidence" in data
        assert "provider" in data
        assert data["response"] == "Тестов отговор от AI"

    def test_chatbot_message_api_no_message(self, client):
        """Тест за chatbot message API без съобщение"""
        response = client.post("/api/chatbot/message", json={})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_volunteer_logout(self, authenticated_volunteer_client):
        """Тест за volunteer logout"""
        client = authenticated_volunteer_client
        response = client.get("/volunteer_logout")

        assert response.status_code == 302  # Redirect
        # Проверяваме че сесията е изчистена в следващите тестове

    def test_update_volunteer_settings_authenticated(
        self, authenticated_volunteer_client
    ):
        """Тест за update volunteer settings като логнат потребител"""
        client = authenticated_volunteer_client
        response = client.post(
            "/update_volunteer_settings", json={"setting1": "value1"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_volunteer_settings_unauthenticated(self, client):
        """Тест за update volunteer settings като нelogнат потребител"""
        response = client.post(
            "/update_volunteer_settings", json={"setting1": "value1"}
        )

        assert response.status_code == 401


class TestProtectedRoutes:
    """Тестове за защитени routes"""

    def test_admin_dashboard_requires_auth(self, client):
        """Тест че admin dashboard изисква authentication"""
        response = client.get("/admin_dashboard")

        assert response.status_code == 302  # Redirect to login

    def test_admin_dashboard_authenticated(self, authenticated_admin_client):
        """Тест за admin dashboard като логнат admin"""
        client = authenticated_admin_client
        response = client.get("/admin_dashboard")

        assert response.status_code == 200
        assert b"dashboard" in response.data or b"admin" in response.data

    def test_volunteer_dashboard_requires_auth(self, client):
        """Тест че volunteer dashboard изисква authentication"""
        response = client.get("/volunteer_dashboard")

        assert response.status_code == 302  # Redirect to login

    def test_volunteer_dashboard_authenticated(self, authenticated_volunteer_client):
        """Тест за volunteer dashboard като логнат volunteer"""
        client = authenticated_volunteer_client
        response = client.get("/volunteer_dashboard")

        assert response.status_code == 200
        assert b"dashboard" in response.data or b"volunteer" in response.data

    def test_admin_volunteers_requires_auth(self, client):
        """Тест че admin volunteers изисква authentication"""
        response = client.get("/admin_volunteers")

        assert response.status_code == 302  # Redirect to login

    def test_admin_volunteers_authenticated(self, authenticated_admin_client):
        """Тест за admin volunteers като логнат admin"""
        client = authenticated_admin_client
        response = client.get("/admin_volunteers")

        assert response.status_code == 200


class TestRateLimiting:
    """Тестове за rate limiting"""

    def test_volunteer_register_rate_limit(self, client):
        """Тест за rate limiting на volunteer register"""
        # Този тест може да бъде сложен за имплементация в unit тестове
        # Затова го оставяме като placeholder
        pass

    def test_submit_request_rate_limit(self, client):
        """Тест за rate limiting на submit request"""
        # Този тест може да бъде сложен за имплементация в unit тестове
        # Затова го оставяме като placeholder
        pass


class TestErrorHandlers:
    """Тестове за error handlers"""

    def test_404_error_handler_html(self, client):
        """Тест за 404 error handler - HTML response"""
        response = client.get("/nonexistent-page")

        assert response.status_code == 404
        assert b"404" in response.data
        assert "не е намерена".encode("utf-8") in response.data

    def test_404_error_handler_json(self, client):
        """Тест за 404 error handler - JSON response"""
        response = client.get("/api/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"
        assert data["status_code"] == 404

    def test_403_error_handler_html(self, client):
        """Тест за 403 error handler - HTML response"""
        # Този тест изисква route който връща 403
        # За сега оставяме като placeholder
        pass

    def test_403_error_handler_json(self, client):
        """Тест за 403 error handler - JSON response"""
        # Този тест изисква API route който връща 403
        # За сега оставяме като placeholder
        pass

    def test_429_error_handler_html(self, client):
        """Тест за 429 error handler - HTML response"""
        # Този тест изисква rate limited route
        # За сега оставяме като placeholder
        pass

    def test_429_error_handler_json(self, client):
        """Тест за 429 error handler - JSON response"""
        # Този тест изисква rate limited API route
        # За сега оставяме като placeholder
        pass
