def test_social_requests_pages(client, init_test_data, db_session):
    from backend.models import SocialRequest, User

    structure = init_test_data["structure"]

    r = client.get("/requests/new")
    assert r.status_code == 200

    resp = client.post(
        "/requests/new",
        data={
            "structure_id": str(structure.id),
            "need_type": "aide_alimentaire",
            "urgency": "medium",
            "person_ref": "Dossier #A-1",
            "description": "Besoin alimentaire urgent.",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location", "")
    assert "/requests/" in location

    r2 = client.get("/requests")
    assert r2.status_code == 200

    detail_path = location
    if detail_path.startswith("http://") or detail_path.startswith("https://"):
        detail_path = "/" + detail_path.split("/", 3)[-1]
    r3 = client.get(detail_path)
    assert r3.status_code == 200

    req_id = int(detail_path.rstrip("/").split("/")[-1])
    user = User.query.filter_by(email="social.assign@test.local").first()
    if not user:
        user = User(
            username="social_assign_test_user",
            email="social.assign@test.local",
            password_hash="x",
            role="admin",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

    assign_resp = client.post(
        f"/requests/{req_id}/assign",
        data={"assigned_to_user_id": str(user.id)},
        follow_redirects=False,
    )
    assert assign_resp.status_code in (302, 303)

    sr = SocialRequest.query.get(req_id)
    assert sr is not None
    assert sr.assigned_to_user_id == user.id
    assert sr.assigned_at is not None
    assert sr.status == "in_progress"

    unassign_resp = client.post(
        f"/requests/{req_id}/unassign",
        follow_redirects=False,
    )
    assert unassign_resp.status_code in (302, 303)

    sr2 = SocialRequest.query.get(req_id)
    assert sr2 is not None
    assert sr2.assigned_to_user_id is None
    assert sr2.assigned_at is None

    status_resp = client.post(
        f"/requests/{req_id}/status",
        data={"status": "in_progress"},
        follow_redirects=False,
    )
    assert status_resp.status_code in (302, 303)

    sr3 = SocialRequest.query.get(req_id)
    assert sr3 is not None
    assert sr3.status == "in_progress"


def test_dashboard(client):
    r = client.get("/requests/dashboard")
    assert r.status_code == 200
