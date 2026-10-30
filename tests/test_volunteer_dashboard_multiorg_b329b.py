from backend.models import Request, Structure, VolunteerStructureMembership
from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest


def _dashboard_fixture(session, init_test_data):
    volunteer = init_test_data["volunteer"]
    volunteer.volunteer_onboarded = True
    volunteer.location = "Paris"
    volunteer.availability = "weekends"
    structure_a = init_test_data["structure"]
    structure_b = Structure(name="Dashboard B", slug="dashboard-b")
    session.add(structure_b)
    session.flush()
    req_a = Request(
        title="Request visible A", status="open", structure_id=structure_a.id, city="Paris"
    )
    req_b = Request(
        title="Request visible B", status="open", structure_id=structure_b.id, city="Paris"
    )
    session.add_all([req_a, req_b])
    session.flush()
    session.add_all(
        [
            VolunteerStructureMembership(
                volunteer_id=volunteer.id, structure_id=structure_a.id, status="approved"
            ),
            VolunteerStructureMembership(
                volunteer_id=volunteer.id, structure_id=structure_b.id, status="approved"
            ),
        ]
    )
    session.commit()
    return volunteer, structure_a, structure_b, req_a, req_b


def test_dashboard_shows_multiple_approved_structures_and_hides_revoked_structure(
    session, init_test_data, authenticated_volunteer_client
):
    _volunteer, _a, structure_b, req_a, req_b = _dashboard_fixture(session, init_test_data)
    page = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert page.status_code == 200
    assert req_a.title.encode() in page.data
    assert req_b.title.encode() in page.data

    membership_b = VolunteerStructureMembership.query.filter_by(
        volunteer_id=init_test_data["volunteer"].id, structure_id=structure_b.id
    ).one()
    membership_b.status = "revoked"
    session.commit()
    page = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert page.status_code == 200
    assert req_a.title.encode() in page.data
    assert req_b.title.encode() not in page.data


def test_historical_interest_is_hidden_without_current_membership(
    session, init_test_data, authenticated_volunteer_client
):
    volunteer, _a, structure_b, _req_a, req_b = _dashboard_fixture(session, init_test_data)
    interest = VolunteerInterest(
        volunteer_id=volunteer.id, request_id=req_b.id, status="approved"
    )
    session.add(interest)
    session.commit()
    membership_b = VolunteerStructureMembership.query.filter_by(
        volunteer_id=volunteer.id, structure_id=structure_b.id
    ).one()
    membership_b.status = "suspended"
    session.commit()
    page = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert page.status_code == 200
    assert req_b.title.encode() not in page.data
    assert VolunteerInterest.query.filter_by(id=interest.id).count() == 1
