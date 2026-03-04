def test_requests_table_headers(authenticated_admin_client):
    r = authenticated_admin_client.get("/admin/requests")
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    for header in [
        "ID",
        "Title",
        "Name",
        "Status",
        "Priority",
        "Category",
        "Created",
        "Closed",
    ]:
        assert header in html
