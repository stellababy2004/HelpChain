from pathlib import Path

from backend.helpchain_backend.src.models import ProfessionalLead


def test_lead_capture_persists_email_and_deduplicates(client, db_session):
    payload = {"email": "First.Step@Example.org", "source": "lead_capture_popup"}

    first = client.post("/api/lead-capture", json=payload)
    second = client.post("/api/lead-capture", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    lead = ProfessionalLead.query.filter_by(email="first.step@example.org").one()
    assert lead.source == "lead_capture"
    assert lead.status == "new"
    assert ProfessionalLead.query.filter_by(email="first.step@example.org").count() == 1


def test_lead_capture_rejects_invalid_email(client):
    response = client.post("/api/lead-capture", json={"email": "invalid"})
    assert response.status_code == 400


def test_lead_capture_backend_failure_has_no_success_response(client, monkeypatch):
    from backend.helpchain_backend.src.routes import main

    def fail_commit():
        raise RuntimeError("test failure")

    monkeypatch.setattr(main.db.session, "commit", fail_commit)
    response = client.post("/api/lead-capture", json={"email": "fail@example.org"})
    assert response.status_code == 500
    assert response.get_json()["ok"] is False


def test_contact_prefills_session_email_without_url_parameter(client):
    with client.session_transaction() as session:
        session["lead_capture_email"] = "prefill@example.org"

    response = client.get("/contact")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'value="prefill@example.org"' in html
    assert "prefill@example.org" not in response.request.query_string.decode()
    with client.session_transaction() as session:
        assert "lead_capture_email" not in session


def test_lead_capture_frontend_uses_contact_anchor_and_explicit_success_guard():
    source = Path("static/js/lead-capture.js").read_text(encoding="utf-8")
    assert 'href="/contact#intake-form"' in source
    assert "!response.ok || !result.ok" in source
    assert "setTimeout" not in source
    assert "scrollThreshold" not in source


def test_offre_pilot_cta_keeps_demo_fallback_and_is_captured_by_lead_script():
    template = Path("templates/offre.html").read_text(encoding="utf-8")
    source = Path("static/js/lead-capture.js").read_text(encoding="utf-8")

    assert 'href="/demo"' in template
    assert 'a[data-hc-intent="pilot"], a[href="/demo"]' in source
    assert "showCapture(true)" in source
