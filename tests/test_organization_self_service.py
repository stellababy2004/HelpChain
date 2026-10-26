from datetime import timedelta

from backend.models import AdminUser, Structure, utc_now
from backend.helpchain_backend.src.models import PendingOrganizationSignup
from backend.helpchain_backend.src.services.organization_self_service import (
    create_pending_signup,
    verify_and_provision,
)


def _pending(session, *, name="Pilot Org", email="owner@pilot.test"):
    row, token = create_pending_signup(
        organization_name=name,
        contact_name="Owner Pilot",
        email=email,
        password="StrongPass1",
        organization_type="ccas",
    )
    session.commit()
    return row, token


def test_signup_keeps_password_hashed_and_does_not_provision(client, session):
    response = client.post(
        "/creer-workspace",
        data={
            "organization_name": "Pending Pilot",
            "contact_name": "Owner",
            "email": "pending@pilot.test",
            "password": "StrongPass1",
            "organization_type": "ccas",
        },
    )
    assert response.status_code == 200
    pending = PendingOrganizationSignup.query.filter_by(email="pending@pilot.test").one()
    assert pending.password_hash != "StrongPass1"
    assert Structure.query.filter_by(name="Pending Pilot").first() is None
    assert AdminUser.query.filter_by(email="pending@pilot.test").first() is None


def test_verification_provisions_admin_with_password_setup_and_tenant(session):
    _row, token = _pending(session)
    structure, admin = verify_and_provision(token)
    session.commit()
    assert structure.organization_type == "ccas"
    assert admin.role == "admin"
    assert admin.structure_id == structure.id
    assert admin.must_change_password is True


def test_invalid_expired_and_reused_tokens_fail_closed(session):
    row, token = _pending(session, name="Expired Pilot", email="expired@pilot.test")
    row.expires_at = utc_now() - timedelta(minutes=1)
    session.commit()
    try:
        verify_and_provision(token)
        assert False
    except ValueError:
        pass

    row2, token2 = _pending(session, name="Used Pilot", email="used@pilot.test")
    verify_and_provision(token2)
    session.commit()
    try:
        verify_and_provision(token2)
        assert False
    except ValueError:
        pass


def test_verification_redirects_to_canonical_login(client, session):
    _row, token = _pending(session, name="Redirect Pilot", email="redirect@pilot.test")
    response = client.get(f"/creer-workspace/verify/{token}", follow_redirects=False)
    assert response.status_code == 303
    assert "/admin/login" in response.headers["Location"]
    assert "onboarding" in response.headers["Location"]
