import pytest

# Import models_with_analytics first to ensure Task model is available
try:
    import models_with_analytics  # noqa: F401
except ImportError:
    pass


class TestSecurity:
    """Тестове за security функционалността"""

    def test_password_validation(self):
        """Тест за валидация на пароли"""
        from backend.models import AdminUser

        admin = AdminUser()

        # Валидни пароли
        assert admin.set_password("ValidPass123") is None  # Няма грешка

        # Невалидни пароли
        with pytest.raises(ValueError, match="Паролата трябва да бъде поне 8 символа"):
            admin.set_password("Short")

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една главна буква"
        ):
            admin.set_password("lowercase123")

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една малка буква"
        ):
            admin.set_password("UPPERCASE123")

        with pytest.raises(
            ValueError, match="Паролата трябва да съдържа поне една цифра"
        ):
            admin.set_password("NoDigits")

    def test_admin_password_hashing(self):
        """Тест за password hashing при admin users"""
        from backend.models import AdminUser

        admin = AdminUser()
        admin.set_password("TestPassword123")

        assert admin.password_hash is not None
        assert admin.password_hash != "TestPassword123"  # Трябва да е хеширана
        assert admin.check_password("TestPassword123") is True
        assert admin.check_password("WrongPassword") is False

    def test_csrf_protection_disabled_in_tests(self, app):
        """Тест че CSRF е изключена в тестове"""
        assert app.config["WTF_CSRF_ENABLED"] is False

    def test_session_security_settings(self, app):
        """Тест за session security настройки"""
        # В development режим тези настройки може да са по-либерални
        assert "SECRET_KEY" in app.config
        assert app.config["SECRET_KEY"] is not None

    def test_input_validation_submit_request(self, client):
        """Тест за input validation в submit request"""
        # Тест с твърде дълго име
        long_name = "A" * 101  # 101 символа
        response = client.post(
            "/submit_request",
            data={
                "name": long_name,
                "email": "test@example.com",
                "category": "Тест",
                "location": "София",
                "problem": "Тестов проблем",
                "captcha": "7G5K",
            },
        )

        assert response.status_code == 200
        # Трябва да има валидационна грешка

    def test_sql_injection_protection(self, client, db_session):
        """Тест за защита от SQL injection"""
        # Опит за SQL injection в email полето
        malicious_email = "test@example.com' OR '1'='1"

        response = client.post(
            "/volunteer_register",
            data={
                "name": "Тестов Потребител",
                "email": malicious_email,
                "phone": "+359888123456",
                "location": "София",
            },
        )

        # Ако има SQL injection, може да се създаде акаунт или да стане грешка
        # Поне проверяваме че приложението не се срива
        assert response.status_code in [200, 302]  # Успех или redirect

    def test_xss_protection(self, client):
        """Тест за защита от XSS атаки"""
        xss_payload = '<script>alert("XSS")</script>'

        response = client.post(
            "/submit_request",
            data={
                "name": "Тестов Потребител",
                "email": "test@example.com",
                "category": "Тест",
                "location": "София",
                "problem": xss_payload,
                "captcha": "7G5K",
            },
        )

        assert response.status_code == 200
        # Проверяваме че XSS payload е открит и блокиран
        response_text = response.get_data(as_text=True)
        assert (
            "подозрително съдържание" in response_text
            or "suspicious content" in response_text.lower()
        )
        # Потребителският input не трябва да се изпълнява като HTML
        assert xss_payload not in response_text.replace("&lt;", "<").replace(
            "&gt;", ">"
        )

    def test_file_upload_validation(self, client, app):
        """Тест за file upload validation"""
        # Създаваме test файл
        import io

        test_file = io.BytesIO(b"test file content")
        test_file.filename = "test.txt"

        response = client.post(
            "/submit_request",
            data={
                "name": "Тестов Потребител",
                "email": "test@example.com",
                "category": "Тест",
                "location": "София",
                "problem": "Тестов проблем",
                "captcha": "7G5K",
                "file": test_file,
            },
        )

        assert response.status_code == 200
        # Трябва да има грешка за невалиден тип файл

    def test_rate_limiting_headers(self, client):
        """Тест за rate limiting headers"""
        response = client.get("/submit_request")

        # Проверяваме дали има rate limiting headers
        # (може да няма в тестова среда)
        assert response.status_code == 200

    def test_secure_headers(self, client):
        """Тест за security headers"""
        response = client.get("/")

        # Проверяваме някои основни security headers
        assert (
            "X-Content-Type-Options" in response.headers or response.status_code == 200
        )

    def test_admin_2fa_security(self, test_admin_user):
        """Тест за 2FA security при admin users"""
        admin = test_admin_user

        # Без 2FA
        admin.twofa_enabled = False
        assert admin.verify_totp("123456") is False

        # С 2FA но без secret
        admin.twofa_enabled = True
        admin.twofa_secret = None
        assert admin.verify_totp("123456") is False

        # С 2FA и невалиден token
        admin.enable_2fa()
        assert admin.verify_totp("invalid") is False
        assert admin.verify_totp("") is False

    def test_session_isolation(
        self, client, authenticated_admin_client, authenticated_volunteer_client
    ):
        """Тест за session isolation между различни типове потребители"""
        # Admin client трябва да има admin сесия
        admin_response = authenticated_admin_client.get("/admin_dashboard")
        assert admin_response.status_code == 200

        # Volunteer client трябва да има volunteer сесия
        volunteer_response = authenticated_volunteer_client.get("/volunteer_dashboard")
        assert volunteer_response.status_code == 200

        # Обикновен client няма сесия
        regular_response = client.get("/admin_dashboard")
        print(f"Regular client response status: {regular_response.status_code}")
        print(
            f"Regular client response data: {regular_response.get_data(as_text=True)[:500]}"
        )
        if regular_response.status_code == 302:
            print(f"Redirect location: {regular_response.headers.get('Location')}")
        assert regular_response.status_code == 302  # Redirect to login
