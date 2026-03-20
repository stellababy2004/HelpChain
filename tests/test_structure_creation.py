from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser, Structure


def _login_admin_session(client, admin_id: int):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = admin_id


def test_structure_creation_creates_admin_and_structure(client, app):
    with app.app_context():
        superadmin = AdminUser(
            username="superadmin",
            email="superadmin@test.local",
            password_hash="x",
            role="superadmin",
            is_active=True,
        )
        db.session.add(superadmin)
        db.session.commit()
        admin_id = superadmin.id

    _login_admin_session(client, admin_id)

    resp = client.post(
        "/admin/create-structure",
        json={
            "name": "CCAS Boulogne",
            "admin_email": "admin@ccas-boulogne.fr",
            "password": "TempPass1",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "structure_id" in data
    assert "admin_id" in data

    with app.app_context():
        structure = db.session.get(Structure, data["structure_id"])
        admin = db.session.get(AdminUser, data["admin_id"])

        assert structure is not None
        assert admin is not None
        assert admin.role == "admin"
        assert admin.structure_id == structure.id
