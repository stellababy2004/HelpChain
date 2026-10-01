from backend.extensions import db
from backend.models import User
from backend.helpchain_backend.src.models import Structure


def test_legacy_organization_registration_requires_global_admin(client, app):
    resp = client.post(
        "/create-organization",
        json={
            "organization_name": "CCAS Boulogne",
            "admin_email": "admin@ccas-boulogne.fr",
            "admin_name": "Marie Dupont",
            "password": "SecureTempPassword123",
        },
    )
    assert resp.status_code == 403

    with app.app_context():
        assert Structure.query.filter_by(name="CCAS Boulogne").first() is None
        admin = (
            db.session.query(User)
            .filter_by(email="admin@ccas-boulogne.fr")
            .first()
        )
        assert admin is None


def test_legacy_organization_registration_uses_canonical_global_flow(client, app):
    from tests.test_admin_team import _admin, _login

    admin = _admin("global_registration", None, "superadmin")
    db.session.commit()
    _login(client, app, admin)
    response = client.post("/create-organization", json={"password": "NeverUseThis123"})
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/admin/structures/new")
