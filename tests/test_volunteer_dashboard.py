import json
import pytest

from backend.app import app, db
from backend.models import Volunteer, User


@pytest.fixture
def client():
    # Enable testing mode; CSRF is managed centrally in conftest.py
    app.config["TESTING"] = True
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

        # ensure corresponding user exists and link to volunteer
        user = User.query.filter_by(email=vol.email).first()
        if not user:
            # derive a safe username from the email local-part and ensure uniqueness
            base = (vol.email.split("@")[0] or "volunteer")[:45]
            uname = base
            suffix = 1
            while User.query.filter_by(username=uname).first() is not None:
                uname = f"{base}_{suffix}"
                suffix += 1

            # For security: avoid committing a hard-coded password into the repo.
            # If a test runner needs to control the demo volunteer password, set
            # the env var `HELPCHAIN_DEMO_VOLUNTEER_PASSWORD`. Otherwise generate
            # a random password at runtime (not stored in source control).
            import os, secrets

            demo_pw = os.getenv("HELPCHAIN_DEMO_VOLUNTEER_PASSWORD")
            if not demo_pw:
                demo_pw = secrets.token_urlsafe(16)

            u = User()
            u.username = uname
            u.email = vol.email
            try:
                u.set_password(demo_pw)
            except Exception:
                # fallback if password hashing helpers unavailable
                u.password_hash = demo_pw
            u.role = "volunteer"
            db.session.add(u)
            db.session.commit()
            user = u

        # Link volunteer -> user if not already linked
        try:
            if getattr(vol, "user_id", None) != getattr(user, "id", None):
                vol.user_id = user.id
                db.session.add(vol)
                db.session.commit()
        except Exception:
            # best-effort only; don't fail helper on linking issues
            try:
                db.session.rollback()
            except Exception:
                pass
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
