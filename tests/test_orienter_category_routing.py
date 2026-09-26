def test_orienter_links_use_canonical_request_categories(client):
    response = client.get("/orienter")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    expected_links = (
        "/submit_request?category=food",
        "/submit_request?category=admin_help",
        "/submit_request?category=isolation",
        "/submit_request?category=health",
        "/submit_request?category=emergency",
    )

    for link in expected_links:
        assert link in html

    assert "/submit_request?domain=" not in html


def test_submit_request_preselects_category_from_orienter(client):
    response = client.get("/submit_request?category=isolation")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert 'value="isolation" selected' in html
