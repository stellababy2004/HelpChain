from tests.test_admin_intervenant_detail_routes import _login_admin


def test_professionals_map_has_no_hardcoded_boulogne_default(app, session):
    from backend.models import AdminUser
    from werkzeug.security import generate_password_hash

    superadmin = AdminUser(
        username="professionals_map_superadmin",
        email="professionals-map-superadmin@test.local",
        password_hash=generate_password_hash("TestPass123!"),
        role="superadmin",
        is_active=True,
    )
    session.add(superadmin)
    session.commit()

    client = app.test_client()
    _login_admin(client, app, superadmin)

    response = client.get("/admin/professionals-map")

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Boulogne-Billancourt" not in html
    assert 'id="proMapZoneSelect"' in html
    assert "Toutes les zones" in html
    assert "city=Boulogne-Billancourt" not in html
