def test_social_requests_pages(client, init_test_data):
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
