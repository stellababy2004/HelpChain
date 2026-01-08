from appy import app


def test_index_route():
    tester = app.test_client()
    response = tester.get("/")
    assert response.status_code == 200
    assert "Добре дошли" in response.data.decode("utf-8")


def test_feedback_route():
    """Test feedback submission with analytics tracking"""
    tester = app.test_client()
    response = tester.post(
        "/feedback",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "message": "This is a test feedback message",
        },
    )

    # Should redirect (status code 302)
    assert response.status_code == 302


