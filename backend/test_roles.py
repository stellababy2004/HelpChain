import requests


def test_admin_roles_dashboard():
    """Тест за достъп до админ роли и права"""
    session = requests.Session()
    response = session.post(
        "http://127.0.0.1:3000/admin_login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 302, f"Админ логин неуспешен: {response.status_code}"

    response2 = session.get("http://127.0.0.1:3000/admin/roles")
    assert (
        response2.status_code == 200
    ), f"Роли dashboard недостъпен: {response2.status_code}"
    content = response2.text
    assert (
        "Роли" in content and "Права" in content
    ), "Съдържанието не съдържа роли и права"
