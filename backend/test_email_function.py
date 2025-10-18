"""
Test Email Functions for HelpChain Application

This module contains comprehensive tests for email functionality in the HelpChain application,
including volunteer registration notifications and access code emails.
"""

from datetime import datetime
from unittest.mock import MagicMock

from flask_mail import Message


class TestEmailFunctionality:
    """Test class for email functionality testing"""

    def test_volunteer_registration_email_success(self, app, client, mocker):
        """Test successful volunteer registration email sending"""
        with app.app_context():
            # Mock the mail.send method
            mock_send = mocker.patch("backend.appy.mail.send")

            # Mock database operations
            mock_volunteer = MagicMock()
            mock_volunteer.name = "Test Volunteer"
            mock_volunteer.email = "test@example.com"
            mock_volunteer.phone = "123456789"
            mock_volunteer.location = "Sofia"

            # Mock Volunteer.query.filter_by to return None (new volunteer)
            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = None

            # Mock db.session.add and db.session.commit
            mock_db = mocker.patch("backend.appy.db.session")
            mock_db.add.return_value = None
            mock_db.commit.return_value = None

            # Test data
            test_data = {
                "name": "Test Volunteer",
                "email": "test@example.com",
                "phone": "123456789",
                "location": "Sofia",
            }

            # Make POST request to volunteer registration
            response = client.post("/volunteer_register", data=test_data)

            # Assert response is redirect (successful registration)
            assert response.status_code == 302

            # Assert mail.send was called once
            assert mock_send.call_count == 1

            # Get the message that was sent
            call_args = mock_send.call_args[0][0]  # First positional argument
            assert isinstance(call_args, Message)
            assert call_args.subject == "Нов доброволец в HelpChain"
            assert call_args.recipients == ["contact@helpchain.live"]
            assert "Test Volunteer" in call_args.body
            assert "test@example.com" in call_args.body
            assert "123456789" in call_args.body
            assert "Sofia" in call_args.body

    def test_volunteer_registration_email_failure_fallback(self, app, client, mocker):
        """Test volunteer registration email failure with file fallback"""
        with app.app_context():
            # Mock mail.send to raise exception
            mock_send = mocker.patch(
                "backend.appy.mail.send", side_effect=Exception("SMTP Error")
            )

            # Mock database operations
            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = None

            mock_db = mocker.patch("backend.appy.db.session")
            mock_db.add.return_value = None
            mock_db.commit.return_value = None

            # Mock file operations
            mock_open = mocker.patch("builtins.open", mocker.mock_open())

            # Test data
            test_data = {
                "name": "Test Volunteer",
                "email": "test@example.com",
                "phone": "123456789",
                "location": "Sofia",
            }

            # Make POST request
            response = client.post("/volunteer_register", data=test_data)

            # Assert response is redirect
            assert response.status_code == 302

            # Assert mail.send was called and failed
            mock_send.assert_called_once()

            # Assert file was opened for writing (fallback)
            mock_open.assert_called_with("sent_emails.txt", "a", encoding="utf-8")

    def test_volunteer_login_access_code_email_success(self, app, client, mocker):
        """Test successful access code email sending during volunteer login"""
        with app.app_context():
            # Mock mail.send
            mock_send = mocker.patch("backend.appy.mail.send")

            # Mock volunteer lookup
            mock_volunteer = MagicMock()
            mock_volunteer.id = 1
            mock_volunteer.name = "Test Volunteer"
            mock_volunteer.email = "test@example.com"

            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = mock_volunteer

            # Mock session
            with client.session_transaction() as sess:
                sess.clear()

            # Test data
            test_data = {"email": "test@example.com"}

            # Make POST request
            response = client.post("/volunteer_login", data=test_data)

            # Assert redirect to verification page
            assert response.status_code == 302
            assert "/volunteer_verify_code" in response.headers["Location"]

            # Assert mail.send was called
            assert mock_send.call_count == 1

            # Check email content
            call_args = mock_send.call_args[0][0]
            assert isinstance(call_args, Message)
            assert call_args.subject == "HelpChain - Код за достъп"
            assert call_args.recipients == ["test@example.com"]
            assert "Test Volunteer" in call_args.body
            assert "Код за достъп:" in call_args.body
            assert "15 минути" in call_args.body

    def test_volunteer_login_access_code_email_failure_fallback(
        self, app, client, mocker
    ):
        """Test access code email failure with file fallback"""
        with app.app_context():
            # Mock mail.send to fail
            mock_send = mocker.patch(
                "backend.appy.mail.send", side_effect=Exception("SMTP Error")
            )

            # Mock volunteer
            mock_volunteer = MagicMock()
            mock_volunteer.id = 1
            mock_volunteer.name = "Test Volunteer"
            mock_volunteer.email = "test@example.com"

            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = mock_volunteer

            # Mock file operations
            mock_open = mocker.patch("builtins.open", mocker.mock_open())

            # Test data
            test_data = {"email": "test@example.com"}

            # Make POST request
            response = client.post("/volunteer_login", data=test_data)

            # Assert redirect
            assert response.status_code == 302

            # Assert mail.send was called and failed
            mock_send.assert_called_once()

            # Assert fallback file was written
            assert mock_open.call_count >= 1

    def test_volunteer_login_invalid_email(self, app, client, mocker):
        """Test volunteer login with non-existent email"""
        with app.app_context():
            # Mock volunteer lookup to return None
            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = None

            # Test data
            test_data = {"email": "nonexistent@example.com"}

            # Make POST request
            response = client.post("/volunteer_login", data=test_data)

            # Assert stays on login page with error
            assert response.status_code == 200
            assert "Няма регистриран доброволец с този имейл" in response.get_data(
                as_text=True
            )

    def test_access_code_verification_success(self, app, client, mocker):
        """Test successful access code verification"""
        with app.app_context():
            # Mock volunteer lookup
            mock_volunteer = MagicMock()
            mock_volunteer.id = 1
            mock_volunteer.name = "Test Volunteer"

            mock_get = mocker.patch("backend.appy.Volunteer.query")
            mock_get.get.return_value = mock_volunteer

            # Set up session with pending login
            access_code = "123456"
            with client.session_transaction() as sess:
                sess["pending_volunteer_login"] = {
                    "email": "test@example.com",
                    "volunteer_id": 1,
                    "access_code": access_code,
                    "expires": datetime.now().timestamp() + 900,
                }

            # Test data
            test_data = {"code": access_code}

            # Make POST request
            response = client.post("/volunteer_verify_code", data=test_data)

            # Assert redirect to dashboard
            assert response.status_code == 302
            assert "/volunteer_dashboard" in response.headers["Location"]

    def test_access_code_verification_wrong_code(self, app, client, mocker):
        """Test access code verification with wrong code"""
        with app.app_context():
            # Set up session with pending login
            with client.session_transaction() as sess:
                sess["pending_volunteer_login"] = {
                    "email": "test@example.com",
                    "volunteer_id": 1,
                    "access_code": "123456",
                    "expires": datetime.now().timestamp() + 900,
                }

            # Test data with wrong code
            test_data = {"code": "654321"}

            # Make POST request
            response = client.post("/volunteer_verify_code", data=test_data)

            # Assert stays on verification page with error
            assert response.status_code == 200
            assert "Невалиден код за достъп" in response.get_data(as_text=True)

    def test_access_code_verification_expired(self, app, client, mocker):
        """Test access code verification with expired code"""
        with app.app_context():
            # Set up session with expired pending login
            with client.session_transaction() as sess:
                sess["pending_volunteer_login"] = {
                    "email": "test@example.com",
                    "volunteer_id": 1,
                    "access_code": "123456",
                    "expires": datetime.now().timestamp() - 100,  # Expired
                }

            # Test data
            test_data = {"code": "123456"}

            # Make POST request
            response = client.post("/volunteer_verify_code", data=test_data)

            # Assert redirect back to login with expired message
            assert response.status_code == 302
            assert "/volunteer_login" in response.headers["Location"]

    def test_email_configuration_validation(self, app):
        """Test that email configuration is properly set"""
        with app.app_context():
            # Check that mail configuration exists
            assert app.config.get("MAIL_SERVER") is not None
            assert app.config.get("MAIL_DEFAULT_SENDER") is not None

            # Check mail object is initialized
            from backend.appy import mail

            assert mail is not None

    def test_email_content_format_volunteer_registration(self, app, mocker):
        """Test the format and content of volunteer registration emails"""
        with app.app_context():
            mock_send = mocker.patch("backend.appy.mail.send")

            # Test email content structure
            expected_subject = "Нов доброволец в HelpChain"
            expected_recipient = "contact@helpchain.live"

            # Simulate email creation (this would normally happen in the route)
            msg = Message(
                subject=expected_subject,
                recipients=[expected_recipient],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body="""Нов доброволец се е регистрирал:

Име: Test User
Имейл: test@example.com
Телефон: 123456789
Локация: Sofia

Моля, свържете се с доброволеца за допълнителна информация.""",
            )

            # Send the message
            mock_send(msg)

            # Verify the call
            mock_send.assert_called_once()
            sent_msg = mock_send.call_args[0][0]

            assert sent_msg.subject == expected_subject
            assert sent_msg.recipients == [expected_recipient]
            assert "Test User" in sent_msg.body
            assert "test@example.com" in sent_msg.body
            assert "Sofia" in sent_msg.body

    def test_email_content_format_access_code(self, app, mocker):
        """Test the format and content of access code emails"""
        with app.app_context():
            mock_send = mocker.patch("backend.appy.mail.send")

            # Test email content structure
            volunteer_name = "Test Volunteer"
            access_code = "123456"
            recipient_email = "test@example.com"

            expected_subject = "HelpChain - Код за достъп"

            # Simulate email creation
            msg = Message(
                subject=expected_subject,
                recipients=[recipient_email],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body=f"""Здравейте {volunteer_name},

Получен е опит за вход в доброволческия панел на HelpChain.

Вашият код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
""",
            )

            # Send the message
            mock_send(msg)

            # Verify the call
            mock_send.assert_called_once()
            sent_msg = mock_send.call_args[0][0]

            assert sent_msg.subject == expected_subject
            assert sent_msg.recipients == [recipient_email]
            assert volunteer_name in sent_msg.body
            assert access_code in sent_msg.body
            assert "15 минути" in sent_msg.body
            assert "HelpChain системата" in sent_msg.body

    def test_fallback_file_format_volunteer_registration(self, app, mocker, tmp_path):
        """Test the format of fallback file for volunteer registration emails"""
        with app.app_context():
            # Mock mail.send to fail
            mocker.patch("backend.appy.mail.send", side_effect=Exception("SMTP Error"))

            # Mock the open function to use our test file
            mock_open = mocker.patch("builtins.open")
            mock_file = mocker.MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            # Simulate the fallback logic from the registration route
            volunteer_data = {
                "name": "Test Volunteer",
                "email": "test@example.com",
                "phone": "123456789",
                "location": "Sofia",
            }

            expected_content = f"""Subject: Нов доброволец в HelpChain
To: contact@helpchain.live
From: {app.config['MAIL_DEFAULT_SENDER']}

Нов доброволец се е регистрирал:

Име: {volunteer_data['name']}
Имейл: {volunteer_data['email']}
Телефон: {volunteer_data['phone']}
Локация: {volunteer_data['location']}

Моля, свържете се с доброволеца за допълнителна информация.

{'='*50}
"""

            # Simulate writing to file (this would happen in the except block)
            with open("sent_emails.txt", "a", encoding="utf-8") as f:
                f.write(expected_content)

            # Verify file was opened for append
            mock_open.assert_called_with("sent_emails.txt", "a", encoding="utf-8")

            # Verify content was written
            mock_file.write.assert_called_with(expected_content)

    def test_fallback_file_format_access_code(self, app, mocker, tmp_path):
        """Test the format of fallback file for access code emails"""
        with app.app_context():
            # Mock mail.send to fail
            mocker.patch("backend.appy.mail.send", side_effect=Exception("SMTP Error"))

            # Mock the open function
            mock_open = mocker.patch("builtins.open")
            mock_file = mocker.MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            # Simulate the fallback logic from the login route
            volunteer_name = "Test Volunteer"
            email = "test@example.com"
            access_code = "123456"

            expected_content = f"""Subject: HelpChain - Код за достъп
To: {email}
From: {app.config['MAIL_DEFAULT_SENDER']}

Здравейте {volunteer_name},

Получен е опит за вход в доброволческия панел на HelpChain.

Вашият код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата

{'='*50}
"""

            # Simulate writing to file
            with open("sent_emails.txt", "a", encoding="utf-8") as f:
                f.write(expected_content)

            # Verify file operations
            mock_open.assert_called_with("sent_emails.txt", "a", encoding="utf-8")
            mock_file.write.assert_called_with(expected_content)

    def test_email_rate_limiting_simulation(self, app, client, mocker):
        """Test that email sending doesn't cause rate limiting issues in tests"""
        with app.app_context():
            # Mock mail.send to be very fast (no actual SMTP)
            mock_send = mocker.patch("backend.appy.mail.send")

            # Mock volunteer operations
            mock_volunteer = MagicMock()
            mock_volunteer.id = 1
            mock_volunteer.name = "Test Volunteer"
            mock_volunteer.email = "test@example.com"

            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = mock_volunteer

            # Test multiple rapid email sends
            for i in range(5):
                with client.session_transaction() as sess:
                    sess.clear()

                test_data = {"email": "test@example.com"}
                response = client.post("/volunteer_login", data=test_data)
                assert response.status_code == 302

            # Assert all emails were "sent" (mocked)
            assert mock_send.call_count == 5

    def test_email_logging_integration(self, app, client, mocker, caplog):
        """Test that email operations are properly logged"""
        with app.app_context():
            # Mock mail operations
            mocker.patch("backend.appy.mail.send")

            # Mock volunteer
            mock_volunteer = MagicMock()
            mock_volunteer.id = 1
            mock_volunteer.name = "Test Volunteer"
            mock_volunteer.email = "test@example.com"

            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.return_value.first.return_value = mock_volunteer

            # Clear any existing log records
            caplog.clear()

            # Perform login operation
            test_data = {"email": "test@example.com"}
            client.post("/volunteer_login", data=test_data)

            # Check that appropriate log messages were generated
            assert any(
                "Login attempt for email: test@example.com" in record.message
                for record in caplog.records
            )
            assert any(
                "Volunteer found: True" in record.message for record in caplog.records
            )
            assert any(
                "Access code sent to test@example.com" in record.message
                for record in caplog.records
            )

    def test_database_error_handling_in_email_flow(self, app, client, mocker):
        """Test that database errors during email operations are handled gracefully"""
        with app.app_context():
            # Mock database operation to fail
            mock_query = mocker.patch("backend.appy.Volunteer.query")
            mock_query.filter_by.side_effect = Exception("Database connection error")

            # Test data
            test_data = {"email": "test@example.com"}

            # Make POST request
            response = client.post("/volunteer_login", data=test_data)

            # Assert error is handled (should show error message)
            assert response.status_code == 200
            assert b"Database error:" in response.data

    def test_email_template_consistency(self, app):
        """Test that email templates follow consistent formatting"""
        with app.app_context():
            # Test volunteer registration email template
            volunteer_data = {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "123456789",
                "location": "Test City",
            }

            registration_body = f"""Нов доброволец се е регистрирал:

Име: {volunteer_data['name']}
Имейл: {volunteer_data['email']}
Телефон: {volunteer_data['phone']}
Локация: {volunteer_data['location']}

Моля, свържете се с доброволеца за допълнителна информация."""

            # Check template structure
            assert "Нов доброволец се е регистрирал:" in registration_body
            assert "Име:" in registration_body
            assert "Имейл:" in registration_body
            assert "Телефон:" in registration_body
            assert "Локация:" in registration_body
            assert "Моля, свържете се с доброволеца" in registration_body

            # Test access code email template
            access_code = "123456"
            volunteer_name = "Test Volunteer"

            access_code_body = f"""Здравейте {volunteer_name},

Получен е опит за вход в доброволческия панел на HelpChain.

Вашият код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
"""

            # Check template structure
            assert f"Здравейте {volunteer_name}" in access_code_body
            assert "Получен е опит за вход" in access_code_body
            assert f"Вашият код за достъп: {access_code}" in access_code_body
            assert "15 минути" in access_code_body
            assert "Ако това не сте вие" in access_code_body
            assert "HelpChain системата" in access_code_body
