from backend.models import VolunteerStructureMembership


def _legacy_session(client, volunteer_id):
    with client.session_transaction() as state:
        state["volunteer_logged_in"] = True
        state["volunteer_id"] = volunteer_id


def test_legacy_dashboard_requires_current_approved_membership(
    session, init_test_data, client
):
    volunteer = init_test_data["volunteer"]
    _legacy_session(client, volunteer.id)

    assert client.get("/volunteer_dashboard").status_code == 403
    assert client.post("/update_volunteer_settings", json={}).status_code == 403

    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=init_test_data["structure"].id,
            status="approved",
        )
    )
    session.commit()
    assert client.get("/volunteer_dashboard").status_code == 200
    assert client.post("/update_volunteer_settings", json={}).status_code == 200

    volunteer.is_active = False
    session.commit()
    assert client.get("/volunteer_dashboard").status_code == 302
    assert client.post("/update_volunteer_settings", json={}).status_code == 403
