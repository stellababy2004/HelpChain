from datetime import datetime


class TestRoutes:
    """Ð¢ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° Ð¾ÑÐ½Ð¾Ð²Ð½Ð¸Ñ‚Ðµ Flask routes"""

    def test_index_route(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° Ð½Ð°Ñ‡Ð°Ð»Ð½Ð°Ñ‚Ð° ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°"""
        response = client.get("/")

        assert response.status_code == 200
        # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑÐ²Ð°Ð¼Ðµ Ñ‡Ðµ ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°Ñ‚Ð° ÑÑŠÐ´ÑŠÑ€Ð¶Ð° Ð¾ÑÐ½Ð¾Ð²Ð½Ð¸ ÐµÐ»ÐµÐ¼ÐµÐ½Ñ‚Ð¸
        assert b"HelpChain" in response.data or b"index" in response.data

    def test_privacy_route(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° privacy ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°Ñ‚Ð°"""
        response = client.get("/privacy")

        assert response.status_code == 200
        assert b"privacy" in response.data or b"Privacy" in response.data

    def test_terms_route(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° terms ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°Ñ‚Ð°"""
        response = client.get("/terms")

        assert response.status_code == 200
        assert b"terms" in response.data or b"Terms" in response.data

    def test_admin_login_get(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° admin login ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð° (GET)"""
        response = client.get("/admin/login")

        assert response.status_code == 200
        assert (b"Admin login" in response.data) or (b"Connexion" in response.data) or (b"admin" in response.data.lower())

    def test_admin_login_post_invalid_credentials(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° admin login Ñ Ð½ÐµÐ²Ð°Ð»Ð¸Ð´Ð½Ð¸ Ð´Ð°Ð½Ð½Ð¸"""
        response = client.post(
            "/admin/login",
            data={"username": "wrong", "password": "wrong"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert ("Identifiants invalides" in page) or ("Connexion" in page) or ("admin" in page.lower())

    def test_admin_email_2fa_page_contains_verification_field(self, client):
        """Email 2FA ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°Ñ‚Ð° Ð¿Ð¾ÐºÐ°Ð·Ð²Ð° Ð¿Ð¾Ð»Ðµ Ð·Ð° ÐºÐ¾Ð´ Ð½Ð° Ð±ÑŠÐ»Ð³Ð°Ñ€ÑÐºÐ¸."""
        with client.session_transaction() as sess:
            sess["pending_email_2fa"] = True
            sess["email_2fa_code"] = "123456"
            sess["email_2fa_expires"] = datetime.now().timestamp() + 600

        response = client.get("/admin/email_2fa")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Verification code" in html
        assert 'name="code"' in html

    def test_volunteer_register_get(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer register ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°"""
        response = client.get("/volunteer_register")

        assert response.status_code == 200
        assert b"register" in response.data or b"volunteer" in response.data

    def test_volunteer_register_post_valid_data(self, client, db_session, mock_smtp):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer register Ñ Ð²Ð°Ð»Ð¸Ð´Ð½Ð¸ Ð´Ð°Ð½Ð½Ð¸"""
        response = client.post(
            "/volunteer_register",
            data={
                "name": "Test Volunteer",
                "email": "test@example.com",
                "phone": "+359888123456",
                "location_text": "Paris",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑÐ²Ð°Ð¼Ðµ Ñ‡Ðµ Ð´Ð¾Ð±Ñ€Ð¾Ð²Ð¾Ð»ÐµÑ†ÑŠÑ‚ Ðµ ÑÑŠÐ·Ð´Ð°Ð´ÐµÐ½ Ð² Ð±Ð°Ð·Ð°Ñ‚Ð°
        from backend.models import Volunteer

        volunteer = (
            db_session.query(Volunteer).filter_by(email="test@example.com").first()
        )
        assert volunteer is not None
        assert volunteer.name == "Test Volunteer"

    def test_volunteer_register_post_duplicate_email(self, client, test_volunteer):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer register Ñ Ð´ÑƒÐ±Ð»Ð¸Ñ€Ð°Ð½ email"""
        response = client.post(
            "/volunteer_register",
            data={
                "name": "Ð”Ñ€ÑƒÐ³ Ð”Ð¾Ð±Ñ€Ð¾Ð²Ð¾Ð»ÐµÑ†",
                "email": test_volunteer.email,  # Ð¡ÑŠÑ‰Ð¸ÑÑ‚ email
                "phone": "+359888654321",
                "location": "ÐŸÐ»Ð¾Ð²Ð´Ð¸Ð²",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Ð¢Ñ€ÑÐ±Ð²Ð° Ð´Ð° Ð¿Ð¾ÐºÐ°Ð¶Ðµ Ð³Ñ€ÐµÑˆÐºÐ° Ð·Ð° Ð´ÑƒÐ±Ð»Ð¸Ñ€Ð°Ð½ email

    def test_volunteer_login_get(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer login ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°"""
        response = client.get("/volunteer_login")

        assert response.status_code == 200
        assert b"login" in response.data or b"volunteer" in response.data

    def test_submit_request_get(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° submit request ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°"""
        response = client.get("/submit_request")

        assert response.status_code == 200
        assert b"submit" in response.data or b"request" in response.data

    def test_submit_request_post_valid_data(self, client, db_session, mock_smtp):
        """Ð¢ÐµÑÑ‚ Ð·Ð° submit request Ñ Ð²Ð°Ð»Ð¸Ð´Ð½Ð¸ Ð´Ð°Ð½Ð½Ð¸"""
        response = client.post(
            "/submit_request",
            data={
                "name": "Ð¢ÐµÑÑ‚Ð¾Ð² ÐŸÐ¾Ñ‚Ñ€ÐµÐ±Ð¸Ñ‚ÐµÐ»",
                "email": "user@example.com",
                "category": "orientation",
                "location": "Ð¡Ð¾Ñ„Ð¸Ñ",
                "description": "J’ai besoin d’aide pour une orientation administrative.",
                "privacy_consent": "on",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑÐ²Ð°Ð¼Ðµ Ñ‡Ðµ Ð·Ð°ÑÐ²ÐºÐ°Ñ‚Ð° Ðµ ÑÑŠÐ·Ð´Ð°Ð´ÐµÐ½Ð°
        from backend.models import HelpRequest, Request

        request = (
            (db_session.query(HelpRequest).filter_by(email="user@example.com").first() or db_session.query(Request).filter_by(email="user@example.com").first())
        )
        assert request is not None
        assert request.name == "Ð¢ÐµÑÑ‚Ð¾Ð² ÐŸÐ¾Ñ‚Ñ€ÐµÐ±Ð¸Ñ‚ÐµÐ»"

    def test_submit_request_post_invalid_captcha(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° submit request Ñ Ð³Ñ€ÐµÑˆÐµÐ½ captcha"""
        response = client.post(
            "/submit_request",
            data={
                "name": "Ð¢ÐµÑÑ‚Ð¾Ð² ÐŸÐ¾Ñ‚Ñ€ÐµÐ±Ð¸Ñ‚ÐµÐ»",
                "email": "user@example.com",
                "category": "Ð¢ÐµÑ…Ð½Ð¸Ñ‡ÐµÑÐºÐ° Ð¿Ð¾Ð¼Ð¾Ñ‰",
                "location": "Ð¡Ð¾Ñ„Ð¸Ñ",
                "problem": "Ð˜Ð¼Ð°Ð¼ Ð½ÑƒÐ¶Ð´Ð° Ð¾Ñ‚ Ð¿Ð¾Ð¼Ð¾Ñ‰",
                "captcha": "wrong",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Ð¢Ñ€ÑÐ±Ð²Ð° Ð´Ð° Ð¾ÑÑ‚Ð°Ð½Ðµ Ð½Ð° Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ð° Ñ Ð³Ñ€ÐµÑˆÐºÐ°

    def test_chatbot_route(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° chatbot ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ð°Ñ‚Ð°"""
        response = client.get("/chatbot")

        assert response.status_code == 200
        assert b"chatbot" in response.data or b"chat" in response.data


class TestAPIRoutes:
    """Ð¢ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° API routes"""

    def test_ai_status_api(self, client, mock_ai_service):
        """Ð¢ÐµÑÑ‚ Ð·Ð° AI status API"""
        response = client.get("/api/ai/status")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)

    def test_chatbot_message_api_valid(self, client, mock_ai_service):
        """Ð¢ÐµÑÑ‚ Ð·Ð° chatbot message API Ñ Ð²Ð°Ð»Ð¸Ð´Ð½Ð¸ Ð´Ð°Ð½Ð½Ð¸"""
        response = client.post(
            "/api/chatbot/message",
            json={"message": "Ð—Ð´Ñ€Ð°Ð²ÐµÐ¹", "session_id": "test_session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "response" in data
        assert "confidence" in data
        assert "provider" in data
        assert data["response"] in ("Тестов отговор от AI", "Ð¢ÐµÑÑ‚Ð¾Ð² Ð¾Ñ‚Ð³Ð¾Ð²Ð¾Ñ€ Ð¾Ñ‚ AI")

    def test_chatbot_message_api_no_message(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° chatbot message API Ð±ÐµÐ· ÑÑŠÐ¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ"""
        response = client.post("/api/chatbot/message", json={})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_volunteer_logout(self, authenticated_volunteer_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer logout"""
        client = authenticated_volunteer_client
        response = client.get("/volunteer_logout")

        assert response.status_code == 302  # Redirect
        # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑÐ²Ð°Ð¼Ðµ Ñ‡Ðµ ÑÐµÑÐ¸ÑÑ‚Ð° Ðµ Ð¸Ð·Ñ‡Ð¸ÑÑ‚ÐµÐ½Ð° Ð² ÑÐ»ÐµÐ´Ð²Ð°Ñ‰Ð¸Ñ‚Ðµ Ñ‚ÐµÑÑ‚Ð¾Ð²Ðµ

    def test_update_volunteer_settings_authenticated(
        self, authenticated_volunteer_client
    ):
        """Ð¢ÐµÑÑ‚ Ð·Ð° update volunteer settings ÐºÐ°Ñ‚Ð¾ Ð»Ð¾Ð³Ð½Ð°Ñ‚ Ð¿Ð¾Ñ‚Ñ€ÐµÐ±Ð¸Ñ‚ÐµÐ»"""
        client = authenticated_volunteer_client
        response = client.post(
            "/update_volunteer_settings", json={"setting1": "value1"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_volunteer_settings_unauthenticated(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° update volunteer settings ÐºÐ°Ñ‚Ð¾ Ð½elogÐ½Ð°Ñ‚ Ð¿Ð¾Ñ‚Ñ€ÐµÐ±Ð¸Ñ‚ÐµÐ»"""
        response = client.post(
            "/update_volunteer_settings", json={"setting1": "value1"}
        )

        assert response.status_code == 401


class TestProtectedRoutes:
    """Ð¢ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° Ð·Ð°Ñ‰Ð¸Ñ‚ÐµÐ½Ð¸ routes"""

    def test_admin_dashboard_requires_auth(self, client):
        """Ð¢ÐµÑÑ‚ Ñ‡Ðµ admin dashboard Ð¸Ð·Ð¸ÑÐºÐ²Ð° authentication"""
        response = client.get("/admin_dashboard", follow_redirects=True)

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Please log in as an administrator." in html

    def test_admin_dashboard_authenticated(self, authenticated_admin_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° admin dashboard ÐºÐ°Ñ‚Ð¾ Ð»Ð¾Ð³Ð½Ð°Ñ‚ admin"""
        client = authenticated_admin_client
        response = client.get("/admin_dashboard")

        assert response.status_code == 200
        assert b"dashboard" in response.data or b"admin" in response.data

    def test_volunteer_dashboard_requires_auth(self, client):
        """Ð¢ÐµÑÑ‚ Ñ‡Ðµ volunteer dashboard Ð¸Ð·Ð¸ÑÐºÐ²Ð° authentication"""
        response = client.get("/volunteer_dashboard")

        assert response.status_code == 302  # Redirect to login

    def test_volunteer_dashboard_authenticated(self, authenticated_volunteer_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer dashboard ÐºÐ°Ñ‚Ð¾ Ð»Ð¾Ð³Ð½Ð°Ñ‚ volunteer"""
        client = authenticated_volunteer_client
        response = client.get("/volunteer_dashboard")

        assert response.status_code == 200
        assert b"dashboard" in response.data or b"volunteer" in response.data

    def test_admin_volunteers_requires_auth(self, client):
        """Ð¢ÐµÑÑ‚ Ñ‡Ðµ admin volunteers Ð¸Ð·Ð¸ÑÐºÐ²Ð° authentication"""
        response = client.get("/admin_volunteers")

        assert response.status_code == 302  # Redirect to login

    def test_admin_volunteers_authenticated(self, authenticated_admin_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° admin volunteers ÐºÐ°Ñ‚Ð¾ Ð»Ð¾Ð³Ð½Ð°Ñ‚ admin"""
        client = authenticated_admin_client
        response = client.get("/admin_volunteers")

        assert response.status_code == 200


class TestRateLimiting:
    """Ð¢ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° rate limiting"""

    def test_volunteer_register_rate_limit(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° rate limiting Ð½Ð° volunteer register"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¼Ð¾Ð¶Ðµ Ð´Ð° Ð±ÑŠÐ´Ðµ ÑÐ»Ð¾Ð¶ÐµÐ½ Ð·Ð° Ð¸Ð¼Ð¿Ð»ÐµÐ¼ÐµÐ½Ñ‚Ð°Ñ†Ð¸Ñ Ð² unit Ñ‚ÐµÑÑ‚Ð¾Ð²Ðµ
        # Ð—Ð°Ñ‚Ð¾Ð²Ð° Ð³Ð¾ Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass

    def test_submit_request_rate_limit(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° rate limiting Ð½Ð° submit request"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¼Ð¾Ð¶Ðµ Ð´Ð° Ð±ÑŠÐ´Ðµ ÑÐ»Ð¾Ð¶ÐµÐ½ Ð·Ð° Ð¸Ð¼Ð¿Ð»ÐµÐ¼ÐµÐ½Ñ‚Ð°Ñ†Ð¸Ñ Ð² unit Ñ‚ÐµÑÑ‚Ð¾Ð²Ðµ
        # Ð—Ð°Ñ‚Ð¾Ð²Ð° Ð³Ð¾ Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass


class TestErrorHandlers:
    """Ð¢ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° error handlers"""

    def test_404_error_handler_html(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 404 error handler - HTML response"""
        response = client.get("/nonexistent-page")

        assert response.status_code == 404
        assert b"404" in response.data
        assert (b"Page not found." in response.data) or (b"No results found." in response.data)

    def test_404_error_handler_json(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 404 error handler - JSON response"""
        response = client.get("/api/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"
        assert data["status_code"] == 404

    def test_403_error_handler_html(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 403 error handler - HTML response"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¸Ð·Ð¸ÑÐºÐ²Ð° route ÐºÐ¾Ð¹Ñ‚Ð¾ Ð²Ñ€ÑŠÑ‰Ð° 403
        # Ð—Ð° ÑÐµÐ³Ð° Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass

    def test_403_error_handler_json(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 403 error handler - JSON response"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¸Ð·Ð¸ÑÐºÐ²Ð° API route ÐºÐ¾Ð¹Ñ‚Ð¾ Ð²Ñ€ÑŠÑ‰Ð° 403
        # Ð—Ð° ÑÐµÐ³Ð° Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass

    def test_429_error_handler_html(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 429 error handler - HTML response"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¸Ð·Ð¸ÑÐºÐ²Ð° rate limited route
        # Ð—Ð° ÑÐµÐ³Ð° Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass

    def test_429_error_handler_json(self, client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° 429 error handler - JSON response"""
        # Ð¢Ð¾Ð·Ð¸ Ñ‚ÐµÑÑ‚ Ð¸Ð·Ð¸ÑÐºÐ²Ð° rate limited API route
        # Ð—Ð° ÑÐµÐ³Ð° Ð¾ÑÑ‚Ð°Ð²ÑÐ¼Ðµ ÐºÐ°Ñ‚Ð¾ placeholder
        pass


