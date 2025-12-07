import pytest
import requests


def test_home_page_status():
    """Test if the home page returns a 200 status code."""
    try:
        response = requests.get("http://127.0.0.1:5000/", timeout=5)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    except Exception as e:
        pytest.fail(f"Request to home page failed: {e}")

def test_home_page_content():
    """Test if the home page contains Font Awesome CSS."""
    try:
        response = requests.get("http://127.0.0.1:5000/", timeout=5)
        assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" in response.text, "Font Awesome CSS not found in home page"
    except Exception as e:
        pytest.fail(f"Request to home page failed: {e}")

def test_pytest_integration():
    """Ensure pytest is running and can discover tests."""
    assert True
