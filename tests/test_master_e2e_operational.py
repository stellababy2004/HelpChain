from __future__ import annotations

from datetime import UTC, datetime
import re
from uuid import uuid4

import pyotp

from backend.helpchain_backend.src.models import Case, CaseParticipant, ProfessionalLead
from backend.models import (
    AdminUser,
    Assignment,
    Intervenant,
    Request,
    Structure,
    StructureCoverageArea,
    StructureService,
    User,
)


PASSWORD = "MasterOperationalPass1"


def _structure(session, name: str) -> Structure:
    slug = f"{name.lower().replace(' ', '-')}-{uuid4().hex[:8]}"
    row = Structure(name=name, slug=slug, status="active")
    session.add(row)
    session.flush()
    return row


def _admin(
    session,
    *,
    username: str,
    role: str,
    structure_id: int | None,
    mfa_enabled: bool = True,
):
    row = AdminUser(
        username=username,
        email=f"{username}@test.local",
        role=role,
        structure_id=structure_id,
        is_active=True,
        mfa_enabled=mfa_enabled,
        totp_secret=pyotp.random_base32() if mfa_enabled else None,
    )
    row.set_password(PASSWORD)
    session.add(row)
    session.flush()
    return row


def _public_intake_structure(session, *, name: str) -> Structure:
    structure = session.query(Structure).filter_by(slug="default").first()
    assert structure is not None
    structure.capabilities_json = '["case_management"]'
    if not session.query(StructureCoverageArea).filter_by(
        structure_id=structure.id,
        area_type="city",
        name="Boulogne-Billancourt",
        postal_code="92100",
    ).first():
        session.add(
            StructureCoverageArea(
                structure_id=structure.id,
                area_type="city",
                name="Boulogne-Billancourt",
                postal_code="92100",
                is_active=True,
            )
        )
    if not session.query(StructureService).filter_by(
        structure_id=structure.id, code="orientation"
    ).first():
        session.add(
            StructureService(
                structure_id=structure.id,
                code="orientation",
                name="Orientation",
                is_active=True,
            )
        )
    session.commit()
    return structure


def _submit_public_request(client, suffix: str) -> str:
    title = f"MASTER E2E operational request {suffix}"
    payload = {
        "name": "Master E2E Citizen",
        "email": f"master-e2e-{suffix}@test.local",
        "phone": "0600000000",
        "category": "social",
        "urgency": "normal",
        "title": title,
        "description": "Continuous pilot-readiness operational journey.",
        "location_text": "Boulogne-Billancourt",
        "postcode": "92100",
        "city": "Boulogne-Billancourt",
        "privacy_consent": "1",
        "started_at": str(int(datetime.now(UTC).timestamp() * 1000) - 5000),
    }
    assert client.post("/submit_request", data=payload).status_code == 200
    confirmation = client.post("/submit_request/confirm", data={}, follow_redirects=False)
    assert confirmation.status_code in (302, 303)
    return title


def _real_admin_login(client, admin: AdminUser) -> None:
    login = client.post(
        "/admin/login",
        data={"username": admin.username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert login.status_code in (302, 303)
    location = login.headers.get("Location") or ""
    if admin.mfa_enabled:
        assert "/admin/mfa/verify" in location
        verify = client.post(
            "/admin/mfa/verify",
            data={"code": pyotp.TOTP(admin.totp_secret).now()},
            follow_redirects=False,
        )
        assert verify.status_code in (302, 303)
    else:
        assert "/ops/workspace" in location


def _request_row(session, title: str, structure_id: int) -> Request:
    row = (
        session.query(Request)
        .filter_by(title=title, structure_id=structure_id)
        .order_by(Request.id.desc())
        .first()
    )
    assert row is not None
    assert row.structure_id is not None
    return row


def test_master_e2e_public_request_to_closed_read_only_case(app, session):
    structure_a = _public_intake_structure(session, name="MASTER E2E Structure A")
    structure_b = _structure(session, "MASTER E2E Structure B")
    admin = _admin(
        session,
        username=f"master-operational-admin-{uuid4().hex[:8]}",
        role="admin",
        structure_id=structure_a.id,
    )
    session.commit()

    client = app.test_client()
    title = _submit_public_request(client, uuid4().hex[:10])
    request_row = _request_row(session, title, structure_a.id)
    assert request_row.structure_id == structure_a.id
    assert request_row.structure_id != structure_b.id

    _real_admin_login(client, admin)
    request_list = client.get("/admin/requests")
    assert request_list.status_code == 200
    request_html = request_list.get_data(as_text=True)
    assert title in request_html
    listed_ids = [
        int(value)
        for value in re.findall(r'href="/admin/requests/(\d+)"', request_html)
    ]
    listed_request = (
        session.query(Request)
        .filter(Request.id.in_(listed_ids), Request.title == title)
        .order_by(Request.id.desc())
        .first()
    )
    assert listed_request is not None
    request_row = listed_request

    open_case = client.post(
        f"/admin/requests/{request_row.id}/open-case",
        follow_redirects=False,
    )
    assert open_case.status_code == 303
    case_row = Case.query.filter_by(request_id=request_row.id).one()
    assert case_row.structure_id == structure_a.id

    intervenant = Intervenant(
        structure_id=structure_a.id,
        name="MASTER E2E Eligible Professional",
        email=f"master-professional-{uuid4().hex[:8]}@test.local",
        actor_type="field_referent",
        availability="available",
        is_active=True,
    )
    session.add(intervenant)
    session.flush()
    lead = ProfessionalLead(
        full_name=intervenant.name,
        email=intervenant.email,
        profession="Coordination",
        city="Paris",
        source="test",
        status="new",
        intervenant_id=intervenant.id,
    )
    session.add(lead)
    session.commit()

    assign = client.post(
        f"/admin/cases/{case_row.id}/assign-professional",
        data={"assigned_professional_lead_id": str(lead.id)},
        follow_redirects=False,
    )
    assert assign.status_code == 303
    session.refresh(case_row)
    participant = CaseParticipant.query.filter_by(case_id=case_row.id).one()
    assignment = Assignment.query.filter_by(
        request_id=request_row.id,
        intervenant_id=intervenant.id,
        structure_id=structure_a.id,
    ).one()
    assert case_row.assigned_professional_lead_id == lead.id
    assert participant.participant_type == "professional_lead"
    assert participant.professional_lead_id == lead.id
    assert participant.role == "primary_professional"
    assert participant.status == "active"
    assert assignment.status == "active"

    for status in ("in_progress", "resolved", "closed"):
        response = client.post(
            f"/admin/cases/{case_row.id}/status",
            data={"status": status},
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(case_row)
        assert case_row.status == status

    session.refresh(assignment)
    assert assignment.status == "removed"
    original_state = {
        "status": case_row.status,
        "owner_user_id": case_row.owner_user_id,
        "assigned_professional_lead_id": case_row.assigned_professional_lead_id,
        "priority": case_row.priority,
    }

    mutations = (
        ("assign-owner", {"owner_user_id": str(admin.id)}),
        ("assign-professional", {"assigned_professional_lead_id": str(lead.id)}),
        ("priority", {"priority": "critical"}),
        (
            "participants",
            {
                "participant_type": "external_contact",
                "role": "contributor",
                "status": "active",
                "external_name": "Closed mutation attempt",
            },
        ),
        ("coordination-note", {"message": "Closed mutation attempt"}),
        ("events", {"event_type": "note_added", "message": "Closed mutation attempt"}),
        ("status", {"status": "in_progress"}),
    )
    for endpoint, data in mutations:
        response = client.post(
            f"/admin/cases/{case_row.id}/{endpoint}",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 409, endpoint

    session.refresh(case_row)
    assert {
        "status": case_row.status,
        "owner_user_id": case_row.owner_user_id,
        "assigned_professional_lead_id": case_row.assigned_professional_lead_id,
        "priority": case_row.priority,
    } == original_state

    logout = client.get("/admin/logout", follow_redirects=False)
    assert logout.status_code in (302, 303)
    assert client.get(f"/admin/requests/{request_row.id}").status_code in (302, 303, 401, 403, 404)
    assert client.get(f"/admin/cases/{case_row.id}").status_code in (302, 303, 401, 403, 404)


def test_master_e2e_real_auth_tenant_and_role_guards(app, session):
    structure_a = _public_intake_structure(session, name="MASTER E2E Negative A")
    structure_b = _structure(session, "MASTER E2E Negative B")
    admin_a = _admin(
        session,
        username=f"master-negative-admin-a-{uuid4().hex[:8]}",
        role="admin",
        structure_id=structure_a.id,
    )
    readonly_a = _admin(
        session,
        username=f"master-negative-readonly-{uuid4().hex[:8]}",
        role="readonly",
        structure_id=structure_a.id,
        mfa_enabled=False,
    )
    ops_a = _admin(
        session,
        username=f"master-negative-ops-{uuid4().hex[:8]}",
        role="ops",
        structure_id=structure_a.id,
        mfa_enabled=False,
    )
    requester = User(
        username=f"master-negative-requester-{uuid4().hex[:8]}",
        email=f"master-negative-requester-{uuid4().hex[:8]}@test.local",
        password_hash="x",
        role="requester",
        structure_id=structure_b.id,
        is_active=True,
    )
    session.add(requester)
    session.flush()
    foreign_request = Request(
        title="MASTER E2E foreign request",
        description="Foreign tenant request",
        category="general",
        user_id=requester.id,
        structure_id=structure_b.id,
        status="open",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(foreign_request)
    session.flush()
    foreign_case = Case(
        request_id=foreign_request.id,
        structure_id=structure_b.id,
        status="new",
        priority="normal",
        risk_score=0,
        opened_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(foreign_case)
    foreign_intervenant = Intervenant(
        structure_id=structure_b.id,
        name="Foreign Professional",
        email=f"foreign-professional-{uuid4().hex[:8]}@test.local",
        actor_type="field_referent",
        availability="available",
        is_active=True,
    )
    session.add(foreign_intervenant)
    session.flush()
    foreign_lead = ProfessionalLead(
        full_name=foreign_intervenant.name,
        email=foreign_intervenant.email,
        profession="Coordination",
        source="test",
        status="new",
        intervenant_id=foreign_intervenant.id,
    )
    session.add(foreign_lead)
    local_request = Request(
        title="MASTER E2E local role request",
        description="Local role-policy request",
        category="general",
        user_id=requester.id,
        structure_id=structure_a.id,
        status="open",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(local_request)
    session.flush()
    local_case = Case(
        request_id=local_request.id,
        structure_id=structure_a.id,
        status="new",
        priority="normal",
        risk_score=0,
        opened_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(local_case)
    session.commit()

    client = app.test_client()
    _real_admin_login(client, admin_a)
    assert client.get(f"/admin/requests/{foreign_request.id}").status_code == 404
    assert client.post(
        f"/admin/requests/{foreign_request.id}/status",
        data={"status": "in_progress"},
        follow_redirects=False,
    ).status_code in (403, 404)
    assert client.get(f"/admin/cases/{foreign_case.id}").status_code == 404
    assert client.post(
        f"/admin/cases/{foreign_case.id}/status",
        data={"status": "triaged"},
        follow_redirects=False,
    ).status_code == 404
    assert client.post(
        f"/admin/cases/{foreign_case.id}/assign-professional",
        data={"assigned_professional_lead_id": str(foreign_lead.id)},
        follow_redirects=False,
    ).status_code == 404
    assert client.post(
        f"/admin/cases/{local_case.id}/assign-professional",
        data={"assigned_professional_lead_id": str(foreign_lead.id)},
        follow_redirects=False,
    ).status_code == 409

    readonly_client = app.test_client()
    _real_admin_login(readonly_client, readonly_a)
    assert readonly_client.post(
        f"/admin/cases/{local_case.id}/status",
        data={"status": "triaged"},
        follow_redirects=False,
    ).status_code == 403

    ops_client = app.test_client()
    _real_admin_login(ops_client, ops_a)
    assert ops_client.post(
        f"/admin/cases/{local_case.id}/status",
        data={"status": "triaged"},
        follow_redirects=False,
    ).status_code == 303
    assert ops_client.get("/admin/requests", follow_redirects=False).status_code == 403
