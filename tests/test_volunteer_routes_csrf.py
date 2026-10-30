from backend.models import Request, VolunteerStructureMembership


def _request_with_membership(session, init_test_data):
    volunteer = init_test_data["volunteer"]
    structure = init_test_data["structure"]
    req = Request(
        title="CSRF volunteer request",
        status="in_progress",
        structure_id=structure.id,
        assigned_volunteer_id=volunteer.id,
    )
    session.add(req)
    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=structure.id,
            status="approved",
        )
    )
    session.commit()
    return req, volunteer, structure


def _csrf_token_from_page(client, request_id):
    import re

    page = client.get(f"/volunteer/requests/{request_id}")
    match = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', page.get_data(as_text=True))
    assert match, "CSRF token not rendered"
    return match.group(1)


def test_volunteer_signal_routes_require_csrf(app, session, init_test_data, authenticated_volunteer_client):
    app.config["WTF_CSRF_ENABLED"] = True
    req, _volunteer, _structure = _request_with_membership(session, init_test_data)
    client = authenticated_volunteer_client

    for action in ("can-help", "cant-help"):
        response = client.post(f"/volunteer/requests/{req.id}/{action}")
        assert response.status_code == 400


def test_volunteer_signal_routes_reject_invalid_csrf(app, session, init_test_data, authenticated_volunteer_client):
    app.config["WTF_CSRF_ENABLED"] = True
    req, _volunteer, _structure = _request_with_membership(session, init_test_data)
    client = authenticated_volunteer_client

    for action in ("can-help", "cant-help"):
        response = client.post(
            f"/volunteer/requests/{req.id}/{action}",
            data={"csrf_token": "invalid-token"},
        )
        assert response.status_code == 400


def test_valid_csrf_still_requires_current_membership(app, session, init_test_data, authenticated_volunteer_client):
    app.config["WTF_CSRF_ENABLED"] = True
    req, volunteer, structure = _request_with_membership(session, init_test_data)
    client = authenticated_volunteer_client

    token = _csrf_token_from_page(client, req.id)
    membership = VolunteerStructureMembership.query.filter_by(
        volunteer_id=volunteer.id, structure_id=structure.id
    ).one()
    membership.status = "revoked"
    session.commit()

    before = session.query(Request).filter_by(id=req.id).one().updated_at
    response = client.post(
        f"/volunteer/requests/{req.id}/can-help",
        data={"csrf_token": token},
    )
    assert response.status_code == 404
    assert session.query(Request).filter_by(id=req.id).one().updated_at == before
