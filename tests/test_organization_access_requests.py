from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, OrganizationAccessRequest


def _login_superadmin(client, admin_user):
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_user.id)
        session["user_id"] = admin_user.id
        session["role"] = admin_user.role
        session["is_authenticated"] = True
        session["is_admin"] = True
        session["admin_logged_in"] = True
        session["admin_id"] = admin_user.id


def _make_superadmin(session):
    admin = AdminUser(
        username="org_access_admin",
        email="org-access-admin@test.local",
        password_hash="x",
        role="superadmin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    return admin


def test_demander_acces_get_returns_200(client):
    resp = client.get("/demander-acces")
    assert resp.status_code == 200
    assert b"Demander un acces" in resp.data


def test_demander_acces_valid_post_creates_new_request(client, app):
    resp = client.post(
        "/demander-acces",
        data={
            "organization_name": "CCAS Boulogne",
            "contact_name": "Marie Dupont",
            "email": " MARIE.DUPONT@ccas-boulogne.fr ",
            "phone": "01 02 03 04 05",
            "city": "Boulogne-Billancourt",
            "org_type": "CCAS",
            "estimated_users": "12",
            "message": "Pilotage d'un dispositif local.",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/demander-acces?envoye=1" in (resp.headers.get("Location") or "")

    with app.app_context():
        row = OrganizationAccessRequest.query.one()
        assert row.status == "new"
        assert row.organization_name == "CCAS Boulogne"
        assert row.contact_name == "Marie Dupont"
        assert row.email == "marie.dupont@ccas-boulogne.fr"
        assert row.estimated_users == 12


def test_demander_acces_invalid_post_does_not_create_row(client, app):
    resp = client.post(
        "/demander-acces",
        data={
            "organization_name": "",
            "contact_name": "",
            "email": "not-an-email",
            "estimated_users": "douze",
        },
    )
    assert resp.status_code == 400
    assert b"Le nom de la structure est requis" in resp.data

    with app.app_context():
        assert OrganizationAccessRequest.query.count() == 0


def test_admin_organization_access_requests_protected(client):
    resp = client.get("/admin/organizations/requests", follow_redirects=False)
    assert resp.status_code in (302, 303, 403, 404)
    assert resp.status_code != 200


def test_admin_organization_access_requests_authorized(client, session):
    admin = _make_superadmin(session)
    _login_superadmin(client, admin)

    resp = client.get("/admin/organizations/requests", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Demandes d'acces" in resp.data


def test_admin_organization_access_requests_renders_rows(client, session):
    row = OrganizationAccessRequest(
        organization_name="Mairie de Testville",
        contact_name="Jean Martin",
        email="jean.martin@testville.fr",
        city="Testville",
        org_type="Mairie",
        estimated_users=8,
        status="new",
    )
    session.add(row)
    admin = _make_superadmin(session)
    session.commit()
    _login_superadmin(client, admin)

    resp = client.get("/admin/organizations/requests", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Mairie de Testville" in resp.data
    assert b"jean.martin@testville.fr" in resp.data
    assert b"Nouveau" in resp.data
