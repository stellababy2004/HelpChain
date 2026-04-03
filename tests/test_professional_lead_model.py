from backend.helpchain_backend.src.models import ProfessionalLead


def test_professional_lead_defaults_status_to_new(db_session):
    lead = ProfessionalLead(
        email="demo.lead@test.local",
        full_name="Demo Lead",
        profession="Coordinateur",
    )

    db_session.add(lead)
    db_session.commit()

    assert lead.status == "new"
