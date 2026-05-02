from datetime import UTC, datetime

from flask import session as flask_session

from backend.models_with_analytics import AnalyticsEvent
from backend.helpchain_backend.src.models import OrganizationAccessRequest, ProfessionalLead
from backend.helpchain_backend.src.services.prospect_auto_capture import (
    attach_session_intelligence_to_professional_lead,
    extract_audience_context,
)


def _post_access_request(client, suffix="capture"):
    return client.post(
        "/demander-acces",
        data={
            "organization_name": f"CCAS Auto {suffix}",
            "contact_name": "Marie Dupont",
            "email": f"marie.{suffix}@ccas-auto.test",
            "phone": "01 02 03 04 05",
            "city": "Boulogne-Billancourt",
            "org_type": "CCAS",
            "estimated_users": "12",
            "message": "Besoin de qualifier un deploiement HelpChain.",
        },
        follow_redirects=False,
    )


def test_access_request_auto_captures_prior_audience_session(client, session):
    client.get("/offre", headers={"Referer": "https://www.google.fr/search?q=helpchain"})
    client.get("/deploiement")
    client.get("/demander-acces")

    response = _post_access_request(client, "linked")

    assert response.status_code == 303
    row = OrganizationAccessRequest.query.one()
    context = extract_audience_context(row.internal_notes)

    assert context is not None
    assert context["session_id"].startswith("aud_")
    assert context["score"] >= 25
    assert context["temperature"] == "Tres chaud"
    assert context["source"] == "Google"
    assert context["page_count"] == 3
    assert "/offre" in context["pages_viewed"]
    assert "/deploiement" in context["pages_viewed"]
    assert "/demander-acces" in context["pages_viewed"]
    assert context["first_seen_at"]
    assert context["last_seen_at"]
    assert context["intent_flags"]["visited_offre"] is True


def test_access_request_without_prior_session_still_succeeds(client):
    response = _post_access_request(client, "nolink")

    assert response.status_code == 303
    row = OrganizationAccessRequest.query.one()
    assert extract_audience_context(row.internal_notes) is None


def test_professional_lead_can_receive_session_intelligence(client, session):
    session.add(
        AnalyticsEvent(
            event_type="page_view",
            user_session="aud_professional_test",
            page_url="/professionnels",
            referrer="https://chat.openai.com/",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    lead = ProfessionalLead(
        email="pro.capture@test.local",
        profession="Coordinatrice",
        status="new",
    )
    session.add(lead)
    session.flush()
    lead_id = lead.id

    with client.application.test_request_context("/"):
        flask_session["hc_audience_sid"] = "aud_professional_test"
        summary = attach_session_intelligence_to_professional_lead(lead)
    session.commit()
    session.expire_all()

    lead = (
        session.query(ProfessionalLead)
        .filter_by(email="pro.capture@test.local")
        .order_by(ProfessionalLead.id.desc())
        .first()
    )

    if lead is None:
        lead = (
            session.query(ProfessionalLead)
            .order_by(ProfessionalLead.id.desc())
            .first()
        )
    assert lead is not None

    context = extract_audience_context(lead.notes)
    assert summary is not None
    assert context["session_id"] == "aud_professional_test"
    assert context["source"] == "ChatGPT"
    assert "/professionnels" in context["pages_viewed"]


def test_access_request_detail_renders_captured_audience(authenticated_admin_client):
    authenticated_admin_client.get("/offre", headers={"Referer": "https://www.google.fr/search?q=helpchain"})
    authenticated_admin_client.get("/demander-acces")
    _post_access_request(authenticated_admin_client, "detail")
    row = OrganizationAccessRequest.query.one()

    response = authenticated_admin_client.get(f"/admin/organizations/requests/{row.id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Audience avant conversion" in html
    assert "Score radar" in html
    assert "Google" in html
    assert "/offre" in html


def test_revenue_radar_marks_captured_access_request(authenticated_admin_client):
    authenticated_admin_client.get("/offre", headers={"Referer": "https://www.linkedin.com/company/helpchain"})
    authenticated_admin_client.get("/deploiement")
    authenticated_admin_client.get("/demander-acces")
    _post_access_request(authenticated_admin_client, "radar")

    response = authenticated_admin_client.get("/admin/audience-map")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Revenue Radar" in html
    assert "Lie a une demande" in html
    assert "LinkedIn" in html



