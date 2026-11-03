from datetime import timezone

from backend.models import AdminAuditEvent, AdminUser, Structure
from backend.helpchain_backend.src.routes.admin import _utc_now


def _post_data(client, nonce, **overrides):
    data = {
        "operation_nonce": nonce,
        "reason": "Identité vérifiée avec le titulaire",
        "identity_confirmed": "on",
        "delivery_channel": "direct",
    }
    data.update(overrides)
    return data


def _prepare_target(session):
    structure = session.query(Structure).first()
    target = AdminUser(
        username="temporary_target_test",
        email="temporary_target_test@demo.local",
        password_hash="old-hash",
        role="admin",
        is_active=True,
        structure_id=structure.id if structure else None,
        mfa_enabled=False,
    )
    session.add(target)
    session.commit()
    return target


def test_temporary_access_requires_confirmation_and_valid_channel(
    authenticated_admin_client, session
):
    target = _prepare_target(session)
    with authenticated_admin_client.session_transaction() as browser:
        browser["temporary_access_nonce"] = "nonce-test"

    response = authenticated_admin_client.post(
        f"/admin/platform/users/{target.id}/temporary-access",
        data=_post_data(
            authenticated_admin_client,
            "nonce-test",
            identity_confirmed="",
            delivery_channel="unknown",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303
    session.refresh(target)
    assert target.password_hash == "old-hash"
    assert target.must_change_password is False


def test_superadmin_generates_one_time_access_without_secret_in_audit(
    authenticated_admin_client, session
):
    target = _prepare_target(session)
    with authenticated_admin_client.session_transaction() as browser:
        browser["temporary_access_nonce"] = "nonce-test"

    response = authenticated_admin_client.post(
        f"/admin/platform/users/{target.id}/temporary-access",
        data=_post_data(authenticated_admin_client, "nonce-test"),
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    html = response.get_data(as_text=True)
    assert "Accès temporaire généré" in html
    session.refresh(target)
    assert target.must_change_password is True
    assert target.temporary_password_expires_at is not None
    expires_at = target.temporary_password_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > _utc_now()
    event = (
        session.query(AdminAuditEvent)
        .filter_by(action="SUPERADMIN_TEMPORARY_ACCESS_GENERATED", target_id=target.id)
        .one()
    )
    assert event.admin_user_id != target.id
    assert "temporary_password" not in (event.payload or {})
    assert "password" not in (event.payload or {})


def test_temporary_access_rejects_self_and_superadmin_target(
    authenticated_admin_client, session
):
    with authenticated_admin_client.session_transaction() as browser:
        actor_id = browser["admin_id"]
        browser["temporary_access_nonce"] = "nonce-test"
    actor = session.get(AdminUser, actor_id)
    self_response = authenticated_admin_client.post(
        f"/admin/platform/users/{actor.id}/temporary-access",
        data=_post_data(authenticated_admin_client, "nonce-test"),
    )
    assert self_response.status_code == 403

    other = AdminUser(
        username="temporary_superadmin_test",
        email="temporary_superadmin_test@demo.local",
        password_hash="old-hash",
        role="superadmin",
        is_active=True,
    )
    session.add(other)
    session.commit()
    other_response = authenticated_admin_client.post(
        f"/admin/platform/users/{other.id}/temporary-access",
        data=_post_data(authenticated_admin_client, "nonce-test"),
    )
    assert other_response.status_code == 403
