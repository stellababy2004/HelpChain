import pytest


@pytest.fixture
def session_id():
    return "test-session"


@pytest.fixture
def message():
    return "Hello, test message"
