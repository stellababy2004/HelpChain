from backend.models import AdminUser, Structure, db
from backend.scripts.bootstrap_production_minimal import ensure_superadmin


def test_existing_admin_is_not_modified_by_production_bootstrap(
    app, db_schema, monkeypatch
):
    with app.app_context():
        structure = Structure.query.filter_by(slug="default").first()

        admin = AdminUser(
            username="existing_admin",
            email="existing@test.local",
            role="admin",
            is_active=False,
            structure_id=structure.id,
        )
        admin.set_password("OriginalPass123")
        db.session.add(admin)
        db.session.commit()

        original_id = admin.id
        original_password_hash = admin.password_hash
        original_structure_id = admin.structure_id

        monkeypatch.setenv("HC_BOOTSTRAP_ADMIN_USERNAME", "existing_admin")
        monkeypatch.setenv("HC_BOOTSTRAP_ADMIN_EMAIL", "changed@test.local")
        monkeypatch.setenv("HC_BOOTSTRAP_ADMIN_PASSWORD", "ChangedPass123")

        result = ensure_superadmin(dry_run=False)
        db.session.commit()
        db.session.expire_all()

        preserved = db.session.get(AdminUser, original_id)

        assert result.startswith("SKIP admin exists:")
        assert preserved.email == "existing@test.local"
        assert preserved.role == "admin"
        assert preserved.is_active is False
        assert preserved.structure_id == original_structure_id
        assert preserved.password_hash == original_password_hash
        assert preserved.check_password("OriginalPass123")
        assert not preserved.check_password("ChangedPass123")
