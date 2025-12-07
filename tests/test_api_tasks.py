from backend.app import app


def test_api_tasks_returns_sample():
    app.config["TESTING"] = True
    with app.test_client() as client:
        resp = client.get("/api/tasks?status=open&limit=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert data.get("success") is True
        assert "tasks" in data
        assert isinstance(data["tasks"], list)
