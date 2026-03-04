import pytest

pytestmark = pytest.mark.smoke_admin


@pytest.fixture
def admin_login(authenticated_admin_client):
    return authenticated_admin_client


def test_admin_template_failure_is_controlled(app, admin_login, monkeypatch):
    from backend.helpchain_backend.src.routes import admin as admin_routes

    state = {"called": False}

    def boom(*args, **kwargs):
        state["called"] = True
        raise RuntimeError("template boom (test)")

    monkeypatch.setattr(admin_routes, "render_template", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    r = admin_login.get("/admin/requests")

    assert r.status_code in (500, 502, 503)
    assert state["called"] is True

    body = r.get_data(as_text=True).lower()
    assert ("une erreur" in body) or ("error" in body) or ("incident" in body)
    assert "traceback" not in body
    assert "werkzeug debugger" not in body
