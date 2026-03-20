from backend.extensions import db
from backend.models import User
from backend.helpchain_backend.src.models import Structure


def test_organization_registration_creates_structure_and_admin(client, app):
    resp = client.post(
        "/create-organization",
        json={
            "organization_name": "CCAS Boulogne",
            "admin_email": "admin@ccas-boulogne.fr",
            "admin_name": "Marie Dupont",
            "password": "SecureTempPassword123",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "created"

    with app.app_context():
        structure = db.session.get(Structure, data["structure_id"])
        assert structure is not None
        admin = (
            db.session.query(User)
            .filter_by(email="admin@ccas-boulogne.fr")
            .first()
        )
        assert admin is not None
        assert admin.role == "admin"
        assert admin.structure_id == structure.id
