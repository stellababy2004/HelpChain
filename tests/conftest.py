import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# CRITICAL: Import models_with_analytics FIRST to ensure Task model is registered
# before Volunteer model tries to reference it
try:
    import models_with_analytics  # noqa: F401
    from models_with_analytics import Task  # noqa: F401
except ImportError:
    pass

import pytest

# Добавяме helpchain-backend (родител на папката src) в началото на sys.path,
# за да може `import src` да работи
_root = os.path.dirname(__file__)
_src_parent = os.path.join(_root, "helpchain-backend")
if os.path.isdir(_src_parent):
    sys.path.insert(0, _src_parent)

# Добавя текущата папка (backend) в sys.path така че 'appy' да се импортира директно
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Import models_with_analytics first to ensure Task model is available for relationships
try:
    import models_with_analytics  # noqa: F401

    # Force import of Task model to ensure it's registered
    from models_with_analytics import Task  # noqa: F401
except ImportError:
    pass


@pytest.fixture(scope="session", autouse=True)
def setup_models():
    """Setup models before any tests run"""
    try:
        import models_with_analytics  # noqa: F401
    except ImportError:
        pass


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    try:
        from appy import app

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            "sqlite:///:memory:"  # In-memory database for tests
        )
        return app
    except ImportError:
        # Fallback if appy import fails
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test_key"
        return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Create a database session for testing."""
    from appy import db

    with app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def mock_smtp():
    """Mock SMTP server for email testing."""
    with patch("flask_mail.Mail.send") as mock_send:
        mock_send.return_value = True
        yield mock_send


@pytest.fixture
def mock_analytics():
    """Mock analytics service for testing."""
    with patch("analytics_service.analytics_service") as mock_service:
        mock_service.track_event.return_value = True
        yield mock_service


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    mock_service = MagicMock()
    mock_service.generate_response.return_value = {
        "response": "Тестов отговор от AI",
        "confidence": 0.8,
        "provider": "mock",
    }
    mock_service.generate_response_sync.return_value = {
        "response": "Тестов отговор от AI",
        "confidence": 0.8,
        "provider": "mock",
    }
    mock_service.get_ai_status.return_value = {
        "status": "healthy",
        "providers": ["OpenAI GPT", "Google Gemini"],
        "active_provider": "mock",
    }

    # Patch at the app level where it's imported
    with patch("appy.ai_service", mock_service):
        yield mock_service


@pytest.fixture
def test_admin_user(db_session):
    """Create a test admin user."""
    from backend.models import AdminUser

    admin = AdminUser(username="test_admin", email="admin@test.com")
    admin.set_password("TestPass123")
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def test_volunteer(db_session):
    """Create a test volunteer."""
    from backend.models import Volunteer

    volunteer = Volunteer(
        name="Тестов Доброволец",
        email="volunteer@test.com",
        phone="+359888123456",
        location="София",
    )
    db_session.add(volunteer)
    db_session.commit()
    return volunteer


@pytest.fixture
def test_help_request(db_session, test_volunteer):
    """Create a test help request."""
    from backend.models import HelpRequest

    request = HelpRequest(
        title="Тестова заявка за помощ",
        description="Това е тестова заявка за помощ",
        name="Тестов Потребител",
        email="user@test.com",
        message="Нуждая се от помощ с тестване",
        status="pending",
    )
    db_session.add(request)
    db_session.commit()
    return request


@pytest.fixture
def authenticated_admin_client(client, test_admin_user, app):
    """Create a test client with authenticated admin user."""
    with app.test_request_context():
        with client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_user_id"] = test_admin_user.id
            sess["admin_username"] = test_admin_user.username
    return client


@pytest.fixture
def authenticated_volunteer_client(client, test_volunteer, app):
    """Create a test client with authenticated volunteer user."""
    with app.test_request_context():
        with client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = test_volunteer.id
            sess["volunteer_name"] = test_volunteer.name
    return client


@pytest.fixture
def app_context(app):
    """Provide app context for tests that need it."""
    with app.app_context():
        yield


@pytest.fixture
def db_transaction(db_session):
    """Provide a database transaction that rolls back after test."""
    db_session.begin_nested()
    yield db_session
    db_session.rollback()


@pytest.fixture
def temp_upload_file(tmp_path):
    """Create a temporary file for upload testing."""
    file_path = tmp_path / "test_file.png"
    file_path.write_bytes(b"fake png content")
    return file_path


@pytest.fixture
def admin_credentials():
    """Get admin login credentials from environment."""
    return {"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "Admin123")}


@pytest.fixture
def login_admin(client, admin_credentials):
    """Helper to login as admin and return authenticated client."""
    response = client.post(
        "/admin/login", data=admin_credentials, follow_redirects=True
    )
    assert response.status_code == 200
    return client
