from backend.appy import app

def test_index_route_bg():
    tester = app.test_client()
    response = tester.get('/')
    assert response.status_code == 200
    assert "HelpChain works!" in response.data.decode("utf-8")

def test_index_route_en():
    tester = app.test_client()
    response = tester.get('/', headers={"Cookie": "language=en"})
    assert response.status_code == 200
    assert "HelpChain works!" in response.data.decode("utf-8")

def test_index_route_fr():
    tester = app.test_client()
    response = tester.get('/', headers={"Cookie": "language=fr"})
    assert response.status_code == 200
    assert "HelpChain works!" in response.data.decode("utf-8")