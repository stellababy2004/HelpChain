from backend.helpchain_backend.src.models import (
    AdminUser,
    OrganizationAccessRequest,
    Structure,
)


def _login_superadmin(client, admin_user):
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_user.id)
        session["user_id"] = admin_user.id
        session["role"] = admin_user.role
        session["is_authenticated"] = True
        session["is_admin"] = True
        session["admin_logged_in"] = True
        session["admin_id"] = admin_user.id


def _make_superadmin(session, suffix="phase2"):
    admin = AdminUser(
        username=f"org_access_admin_{suffix}",
        email=f"org-access-admin-{suffix}@test.local",
        password_hash="x",
        role="superadmin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    return admin


def _make_access_request(session, suffix="phase2", *, status="new"):
    row = OrganizationAccessRequest(
        organization_name=f"CCAS Phase2 {suffix}",
        contact_name="Marie Dupont",
        email=f"marie.dupont.{suffix}@ccas.test",
        phone="01 02 03 04 05",
        city="Boulogne-Billancourt",
        org_type="CCAS",
        estimated_users=12,
        message="Besoin de coordination institutionnelle.",
        status=status,
    )
    session.add(row)
    session.commit()
    return row


def test_access_request_detail_requires_admin(client, session):
    row = _make_access_request(session, "protected")

    resp = client.get(f"/admin/organizations/requests/{row.id}", follow_redirects=False)

    assert resp.status_code in (302, 303, 403, 404)
    assert resp.status_code != 200


def test_superadmin_can_view_access_request_detail(client, session):
    row = _make_access_request(session, "detail")
    admin = _make_superadmin(session, "detail")
    _login_superadmin(client, admin)

    resp = client.get(f"/admin/organizations/requests/{row.id}", follow_redirects=False)

    assert resp.status_code == 200
    assert b"CCAS Phase2 detail" in resp.data
    assert b"Approuver et creer la structure" in resp.data


def test_approve_creates_structure_admin_and_review_metadata(client, session):
    row = _make_access_request(session, "approve")
    admin = _make_superadmin(session, "approve")
    _login_superadmin(client, admin)

    resp = client.post(
        f"/admin/organizations/requests/{row.id}/approve",
        data={"internal_notes": "Dossier qualifie par l'equipe."},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(row)
    assert row.status == "approved"
    assert row.reviewed_by_admin_id == admin.id
    assert row.reviewed_at is not None
    assert row.internal_notes == "Dossier qualifie par l'equipe."

    structure = Structure.query.filter_by(name="CCAS Phase2 approve").one()
    assert structure.slug == "ccas-phase2-approve"
    assert structure.status == "active"

    org_admin = AdminUser.query.filter_by(email=row.email).one()
    assert org_admin.role == "admin"
    assert org_admin.is_active is True
    assert org_admin.structure_id == structure.id
    assert org_admin.password_hash


def test_reject_updates_status_without_creating_structure(client, session):
    row = _make_access_request(session, "reject")
    admin = _make_superadmin(session, "reject")
    before_count = Structure.query.count()
    _login_superadmin(client, admin)

    resp = client.post(
        f"/admin/organizations/requests/{row.id}/reject",
        data={"internal_notes": "Hors perimetre pour le pilote."},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(row)
    assert row.status == "rejected"
    assert row.reviewed_by_admin_id == admin.id
    assert row.reviewed_at is not None
    assert row.internal_notes == "Hors perimetre pour le pilote."
    assert Structure.query.count() == before_count
    assert AdminUser.query.filter_by(email=row.email).first() is None


def test_need_info_updates_status_without_creating_structure(client, session):
    row = _make_access_request(session, "needinfo")
    admin = _make_superadmin(session, "needinfo")
    before_count = Structure.query.count()
    _login_superadmin(client, admin)

    resp = client.post(
        f"/admin/organizations/requests/{row.id}/need-info",
        data={"internal_notes": "Preciser le service porteur."},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(row)
    assert row.status == "need_info"
    assert row.reviewed_by_admin_id == admin.id
    assert row.reviewed_at is not None
    assert row.internal_notes == "Preciser le service porteur."
    assert Structure.query.count() == before_count
    assert AdminUser.query.filter_by(email=row.email).first() is None


def test_reapprove_does_not_create_duplicates(client, session):
    row = _make_access_request(session, "duplicate")
    admin = _make_superadmin(session, "duplicate")
    _login_superadmin(client, admin)

    first = client.post(
        f"/admin/organizations/requests/{row.id}/approve",
        data={"internal_notes": "Premier accord."},
        follow_redirects=False,
    )
    assert first.status_code == 303
    structures_after_first = Structure.query.count()
    admins_after_first = AdminUser.query.count()

    second = client.post(
        f"/admin/organizations/requests/{row.id}/approve",
        data={"internal_notes": "Nouvel essai."},
        follow_redirects=False,
    )

    assert second.status_code == 303
    assert Structure.query.count() == structures_after_first
    assert AdminUser.query.count() == admins_after_first
    assert Structure.query.filter_by(name="CCAS Phase2 duplicate").count() == 1
    assert AdminUser.query.filter_by(email=row.email).count() == 1
