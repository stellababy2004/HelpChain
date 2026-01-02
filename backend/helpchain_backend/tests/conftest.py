# conftest.py for HelpChain backend tests
# Contains pytest fixtures and test helpers migrated from src/app.py

import pytest
from backend.helpchain_backend.src.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return app.test_client()

# Test helper for feedback route (moved from app.py)
def test_feedback_route(client):
    response = client.post("/feedback", data={
        "name": "Test User",
        "email": "test@example.com",
        "message": "This is a test feedback message"
    })
    assert response.status_code == 302  # Should redirect
