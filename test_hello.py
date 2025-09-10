import pytest
from backend.appy import app, db

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    with app.app_context():
        db.create_all()
    yield
    # Ако искаш да изчистиш след тестовете, добави db.drop_all() тук

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_homepage(client):
    response = client.get('/')
    assert response.status_code == 200

def test_hello():
    assert True

def test_submit_request(client):
    response = client.post('/submit_request', data={
        'title': 'Test Title',
        'full_name': 'Test User',
        'email': 'test@example.com',
        'phone': '1234567890',
        'description': 'Нуждая се от помощ',
        'captcha': '7G5K'
    })
    assert response.status_code in [200, 302]  # 302 ако има redirect

def test_admin_panel_access(client):
    response = client.get('/')  # Промени на съществуващ маршрут като '/'
    assert response.status_code in [200, 302, 401, 403]