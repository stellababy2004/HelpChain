import pytest

from tests.test_structure_creation import _login_admin_session
from backend.extensions import db
from backend.helpchain_backend.src.models import AdminUser


@pytest.mark.parametrize(
    "exception_message, expected_status, expected_error",
    [
        ("structure_name_exists", 400, "structure_name_exists"),
        ("admin_email_exists", 400, "admin_email_exists"),
        ("sensitive database password leaked", 500, "internal_error"),
    ],
)
def test_create_structure_error_does_not_leak_exception(
    client, app, monkeypatch, exception_message, expected_status, expected_error
):
    with app.app_context():
        superadmin = AdminUser(
            username="security_test_superadmin",
            email="security-superadmin@test.local",
            password_hash="x",
            role="superadmin",
            is_active=True,
            mfa_enabled=True,
            totp_secret="test-mfa-secret",
        )
        db.session.add(superadmin)
        db.session.commit()
        admin_id = superadmin.id

    _login_admin_session(client, admin_id)

    from backend.helpchain_backend.src.routes import admin

    def raise_error(*args, **kwargs):
        raise ValueError(exception_message)

    monkeypatch.setattr(admin, "create_structure_with_admin", raise_error)

    response = client.post(
        "/admin/create-structure",
        json={
            "name": "Test Structure",
            "admin_email": "admin@test.local",
            "password": "TempPass1",
        },
    )

    assert response.status_code == expected_status
    assert response.get_json() == {"error": expected_error}
    assert "sensitive database password leaked" not in response.get_data(as_text=True)
