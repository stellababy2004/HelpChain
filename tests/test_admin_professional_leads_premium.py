def test_admin_professional_leads_premium_empty_state(authenticated_admin_client):
    response = authenticated_admin_client.get("/admin/professional-leads")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Pipeline de qualification" in html
    assert "Nouveaux leads" in html
    assert "A qualifier" in html
    assert "Pipeline professionnels" in html
    assert "Aucun lead professionnel pour le moment" in html
