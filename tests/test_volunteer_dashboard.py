import json
import pytest

from backend.app import app, db
from backend.models import Volunteer, User


@pytest.fixture
def client():
    # Enable testing mode and disable CSRF for API tests
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def ensure_demo_volunteer():
    with app.app_context():
        vol = Volunteer.query.filter_by(email="volunteer@example.com").first()
        if vol:
            return vol
        # create volunteer record
        vol = Volunteer()
        vol.name = "Demo Volunteer"
        vol.email = "volunteer@example.com"
        db.session.add(vol)
        db.session.commit()
        # ensure corresponding user exists
        user = User.query.filter_by(email=vol.email).first()
        if not user:
            u = User()
            u.username = "volunteer"
            u.email = vol.email
            try:
                u.set_password("Volunteer123")
            except Exception:
                u.password_hash = "Volunteer123"
            u.role = "volunteer"
            db.session.add(u)
            db.session.commit()
        return vol


def test_volunteer_login_post_redirects(client):
    vol = ensure_demo_volunteer()
    resp = client.post("/volunteer_login", data={"email": vol.email}, follow_redirects=False)
    # demo flow should redirect to /demo/volunteers
    assert resp.status_code in (302, 303, 200)
    if resp.status_code in (302, 303):
        assert "/demo/volunteers" in resp.headers.get("Location", "")


def test_assign_task_api(client):
    # assign a demo task id=1 to the demo volunteer (API is a stub and should return success)
    vol = ensure_demo_volunteer()
    resp = client.post(f"/api/tasks/1/assign/{vol.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True
    assert int(data.get("assigned_to")) == int(vol.id)


def test_update_location_api(client):
    vol = ensure_demo_volunteer()
    payload = {"latitude": 42.6977, "longitude": 23.3219, "location": "Sofia"}
    resp = client.put(f"/api/volunteers/{vol.id}/location", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True
    assert int(data.get("volunteer_id")) == int(vol.id)
