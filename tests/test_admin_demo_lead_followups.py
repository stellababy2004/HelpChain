from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from backend.helpchain_backend.src.models import ProfessionalLead


def test_demo_leads_page_sends_first_followup_only_once(
    authenticated_admin_client,
    db_session,
    monkeypatch,
):
    lead = ProfessionalLead(
        email="first.followup@test.local",
        full_name="First Followup",
        profession="Coordinator",
        source="demo_page",
        status="new",
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.add(lead)
    db_session.commit()

    mock_send = MagicMock()
    monkeypatch.setattr("backend.helpchain_backend.src.routes.admin.mail.send", mock_send)

    response = authenticated_admin_client.get("/admin/professional-leads/demo")
    assert response.status_code == 200

    db_session.refresh(lead)
    assert mock_send.call_count == 1
    assert lead.first_followup_sent_at is not None

    response = authenticated_admin_client.get("/admin/professional-leads/demo")
    assert response.status_code == 200

    db_session.refresh(lead)
    assert mock_send.call_count == 1


def test_demo_leads_page_sends_second_followup_for_contacted_lead(
    authenticated_admin_client,
    db_session,
    monkeypatch,
):
    lead = ProfessionalLead(
        email="second.followup@test.local",
        full_name="Second Followup",
        profession="Coordinator",
        source="demo_page",
        status="contacted",
        created_at=datetime.now(UTC) - timedelta(days=3),
    )
    db_session.add(lead)
    db_session.commit()

    mock_send = MagicMock()
    monkeypatch.setattr("backend.helpchain_backend.src.routes.admin.mail.send", mock_send)

    response = authenticated_admin_client.get("/admin/professional-leads/demo")
    assert response.status_code == 200

    db_session.refresh(lead)
    assert mock_send.call_count == 1
    assert lead.second_followup_sent_at is not None
