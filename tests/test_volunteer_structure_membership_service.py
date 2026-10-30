import pytest

from backend.models import AdminUser, SecurityEvent, Structure, User, Volunteer
from backend.helpchain_backend.src.services.volunteer_structure_memberships import (
    MembershipError,
    approve_membership,
    is_membership_approved,
    request_membership,
    revoke_membership,
    suspend_membership,
)


def _admin(session, *, username, structure_id):
    admin = AdminUser(
        username=username,
        email=f"{username}@test.local",
        password_hash="test",
        role="admin",
        structure_id=structure_id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    return admin


def _login_admin(client, admin):
    with client.session_transaction() as flask_session:
        flask_session["admin_logged_in"] = True
        flask_session["admin_user_id"] = admin.id


def test_membership_service_lifecycle_and_audit(app, session):
    structure = Structure(name="Service A", slug="service-a")
    user = User(
        username="volunteer-service-a",
        email="volunteer-service-a@test.local",
        password_hash="test",
        structure_id=None,
    )
    session.add_all([structure, user])
    session.flush()
    volunteer = Volunteer(name="Volunteer A", user_id=user.id)
    session.add(volunteer)
    admin = _admin(session, username="membership-admin-a", structure_id=structure.id)
    session.commit()
    client = app.test_client()

    membership = request_membership(
        volunteer_id=volunteer.id,
        structure_id=structure.id,
        requester_user_id=user.id,
    )
    session.commit()
    assert membership.status == "pending"

    _login_admin(client, admin)
    with client:
        client.get("/health/live")
        approve_membership(membership_id=membership.id, reason="verified locally")
        session.commit()
        assert is_membership_approved(
            volunteer_id=volunteer.id, structure_id=structure.id
        )

        suspend_membership(membership_id=membership.id, reason="temporary pause")
        session.commit()
        assert not is_membership_approved(
            volunteer_id=volunteer.id, structure_id=structure.id
        )

        approve_membership(membership_id=membership.id)
        revoke_membership(membership_id=membership.id, reason="revoked")
        session.commit()
        assert not is_membership_approved(
            volunteer_id=volunteer.id, structure_id=structure.id
        )
    assert session.query(SecurityEvent).filter(
        SecurityEvent.event_type.like("volunteer_membership.%")
    ).count() == 4


def test_membership_service_rejects_cross_structure_admin(app, session):
    structure_a = Structure(name="Service A2", slug="service-a2")
    structure_b = Structure(name="Service B2", slug="service-b2")
    user = User(
        username="volunteer-service-b",
        email="volunteer-service-b@test.local",
        password_hash="test",
    )
    session.add_all([structure_a, structure_b, user])
    session.flush()
    volunteer = Volunteer(name="Volunteer B", user_id=user.id)
    session.add(volunteer)
    admin_a = _admin(session, username="membership-admin-a2", structure_id=structure_a.id)
    session.commit()
    client = app.test_client()
    _login_admin(client, admin_a)

    membership = request_membership(
        volunteer_id=volunteer.id,
        structure_id=structure_b.id,
        requester_user_id=user.id,
    )
    session.commit()

    with client:
        client.get("/health/live")
        with pytest.raises(MembershipError) as exc:
            approve_membership(membership_id=membership.id)
    assert exc.value.status_code == 403
    session.rollback()
    assert membership.status == "pending"


def test_membership_service_rejects_unverified_identity_and_duplicate(session):
    structure = Structure(name="Service C", slug="service-c")
    user = User(
        username="volunteer-service-c",
        email="volunteer-service-c@test.local",
        password_hash="test",
    )
    session.add_all([structure, user])
    session.flush()
    volunteer = Volunteer(name="Volunteer C", user_id=None)
    session.add(volunteer)
    session.commit()

    with pytest.raises(MembershipError) as exc:
        request_membership(
            volunteer_id=volunteer.id,
            structure_id=structure.id,
            requester_user_id=user.id,
        )
    assert exc.value.status_code == 403
