from datetime import datetime, timedelta, UTC
import re


def _satisfy_privileged_mfa(client, session, admin_user):
    admin_user.mfa_enabled = True
    admin_user.totp_secret = "test-mfa-secret"
    session.commit()
    with client.session_transaction() as sess:
        sess[client.application.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
        sess["mfa_required"] = True
        sess["mfa_ok_until"] = (
            datetime.now(UTC) + timedelta(minutes=30)
        ).isoformat()


def _login_admin(client, admin_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["user_id"] = admin_user.id
        sess["admin_id"] = admin_user.id
        sess["admin_user_id"] = admin_user.id
        sess["role"] = admin_user.role
        sess["is_authenticated"] = True
        sess["is_admin"] = True
        sess["admin_logged_in"] = True


def _make_structure(session, *, structure_id: int, name: str, slug: str):
    from backend.models import Structure

    structure = session.get(Structure, structure_id)
    if structure is None:
        structure = Structure(id=structure_id, name=name, slug=slug)
        session.add(structure)
        session.commit()
    return structure


def _make_user(session, *, username: str, email: str):
    from backend.models import User

    user = User(username=username, email=email, password_hash="x", role="requester")
    session.add(user)
    session.commit()
    return user


def _make_admin(session, *, username: str, email: str, role: str, structure_id=None):
    from backend.models import AdminUser

    admin = AdminUser(
        username=username,
        email=email,
        password_hash="x",
        role=role,
        is_active=True,
        structure_id=structure_id,
    )
    session.add(admin)
    session.commit()
    return admin


def _make_request(
    session,
    *,
    title: str,
    user_id: int,
    structure_id: int,
    status=None,
    owner_id=None,
    priority=None,
    created_at=None,
    updated_at=None,
):
    from backend.models import Request

    req = Request(
        title=title,
        description=f"Description for {title}",
        category="general",
        user_id=user_id,
        structure_id=structure_id,
        status=status,
        owner_id=owner_id,
        priority=priority,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(req)
    session.commit()
    return req


def _make_case(
    session,
    *,
    request_id: int,
    structure_id: int,
    status="new",
    owner_user_id=None,
    priority="normal",
    risk_score=0,
    last_activity_at=None,
    created_at=None,
):
    from backend.helpchain_backend.src.models import Case

    case = Case(
        request_id=request_id,
        structure_id=structure_id,
        status=status,
        owner_user_id=owner_user_id,
        priority=priority,
        risk_score=risk_score,
        last_activity_at=last_activity_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(case)
    session.commit()
    return case


def _workspace_kpi_value(html: str, label: str) -> int:
    pattern = re.compile(
        r'<div class="hc-ops-summary__label">\s*'
        + re.escape(label)
        + r'\s*</div>\s*<div class="hc-ops-summary__value[^"]*">\s*(\d+)\s*</div>',
        re.S,
    )
    match = pattern.search(html)
    assert match, f"KPI label not found: {label}"
    return int(match.group(1))


def _case_row_count(html: str) -> int:
    return html.count('class="hc-case-row')


def test_admin_requests_shows_seeded_requests_even_with_null_and_new_status(client, session):
    _make_structure(session, structure_id=2, name="Structure 2", slug="structure-2")
    _make_structure(session, structure_id=3, name="Structure 3", slug="structure-3")
    user = _make_user(session, username="seed_user", email="seed_user@test.local")
    admin = _make_admin(
        session,
        username="global_admin_visibility",
        email="global_admin_visibility@test.local",
        role="superadmin",
        structure_id=None,
    )
    _login_admin(client, admin)
    _satisfy_privileged_mfa(client, session, admin)

    _make_request(session, title="seed-null-status", user_id=user.id, structure_id=2, status=None)
    _make_request(session, title="seed-new-status", user_id=user.id, structure_id=2, status="new")
    _make_request(session, title="seed-pending-status", user_id=user.id, structure_id=3, status="pending")

    resp = client.get("/admin/requests", follow_redirects=False)

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "seed-null-status" in html
    assert "seed-new-status" in html
    assert "seed-pending-status" in html


def test_operator_dashboard_only_shows_actionable_scoped_requests(client, session):
    structure = _make_structure(session, structure_id=2, name="Structure 2", slug="structure-2")
    _make_structure(session, structure_id=3, name="Structure 3", slug="structure-3")
    user = _make_user(session, username="ops_seed_user", email="ops_seed_user@test.local")
    operator = _make_admin(
        session,
        username="ops_visibility",
        email="ops_visibility@test.local",
        role="ops",
        structure_id=structure.id,
    )
    _login_admin(client, operator)

    now = datetime.now(UTC).replace(tzinfo=None)

    visible_null = _make_request(
        session,
        title="ops-visible-null-status",
        user_id=user.id,
        structure_id=structure.id,
        status=None,
        owner_id=None,
        created_at=now - timedelta(hours=1),
    )
    visible_new = _make_request(
        session,
        title="ops-visible-new-status",
        user_id=user.id,
        structure_id=structure.id,
        status="new",
        owner_id=None,
        created_at=now - timedelta(hours=2),
    )
    hidden_closed = _make_request(
        session,
        title="ops-hidden-closed",
        user_id=user.id,
        structure_id=structure.id,
        status="done",
        owner_id=None,
        created_at=now - timedelta(days=1),
    )
    hidden_other_structure = _make_request(
        session,
        title="ops-hidden-other-structure",
        user_id=user.id,
        structure_id=3,
        status="pending",
        owner_id=None,
        created_at=now - timedelta(hours=3),
    )
    hidden_non_queue = _make_request(
        session,
        title="ops-hidden-owned-normal",
        user_id=user.id,
        structure_id=structure.id,
        status="pending",
        owner_id=operator.id,
        priority="low",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(minutes=10),
    )

    resp = client.get("/ops/workspace", follow_redirects=False)

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "ops-visible-null-status" in html
    assert "ops-visible-new-status" in html
    assert "ops-hidden-closed" not in html
    assert "ops-hidden-other-structure" not in html
    assert "ops-hidden-owned-normal" not in html


def test_ops_workspace_kpis_match_quick_action_case_filters(
    authenticated_admin_client, session
):
    from backend.models import NotificationJob, Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    user = _make_user(
        session,
        username="ops_kpi_user",
        email="ops_kpi_user@test.local",
    )
    operator = _make_admin(
        session,
        username="ops_kpi_owner",
        email="ops_kpi_owner@test.local",
        role="ops",
        structure_id=structure.id,
    )

    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    stale_time = now - timedelta(hours=80)

    critical_req = _make_request(
        session,
        title="ops-kpi-critical",
        user_id=user.id,
        structure_id=structure.id,
        status="open",
        owner_id=operator.id,
        created_at=now,
        updated_at=now,
    )
    _make_case(
        session,
        request_id=critical_req.id,
        structure_id=structure.id,
        owner_user_id=operator.id,
        priority="critical",
        risk_score=90,
        created_at=now,
    )

    unassigned_req = _make_request(
        session,
        title="ops-kpi-unassigned",
        user_id=user.id,
        structure_id=structure.id,
        status="open",
        owner_id=None,
        created_at=now,
        updated_at=now,
    )
    _make_case(
        session,
        request_id=unassigned_req.id,
        structure_id=structure.id,
        owner_user_id=None,
        created_at=now,
    )

    stale_req = _make_request(
        session,
        title="ops-kpi-stale",
        user_id=user.id,
        structure_id=structure.id,
        status="open",
        owner_id=operator.id,
        created_at=stale_time,
        updated_at=stale_time,
    )
    _make_case(
        session,
        request_id=stale_req.id,
        structure_id=structure.id,
        owner_user_id=operator.id,
        last_activity_at=stale_time,
        created_at=stale_time,
    )

    resolved_req = _make_request(
        session,
        title="ops-kpi-resolved-decoy",
        user_id=user.id,
        structure_id=structure.id,
        status="open",
        owner_id=None,
        created_at=stale_time,
        updated_at=stale_time,
    )
    _make_case(
        session,
        request_id=resolved_req.id,
        structure_id=structure.id,
        status="resolved",
        owner_user_id=None,
        priority="critical",
        risk_score=95,
        last_activity_at=stale_time,
        created_at=stale_time,
    )

    session.add(
        NotificationJob(
            channel="email",
            event_type="ops_test",
            recipient="ops-test@example.invalid",
            status="failed",
            structure_id=structure.id,
        )
    )
    session.commit()

    workspace = authenticated_admin_client.get("/ops/workspace", follow_redirects=False)
    assert workspace.status_code == 200
    workspace_html = workspace.get_data(as_text=True)

    critical = authenticated_admin_client.get("/ops/cases?risk=critical")
    unassigned = authenticated_admin_client.get("/ops/cases?owner=none")
    stale = authenticated_admin_client.get("/ops/cases?stale_72h=1")
    failed_notifications = authenticated_admin_client.get("/ops/notifications?status=failed")

    assert critical.status_code == 200
    assert unassigned.status_code == 200
    assert stale.status_code == 200
    assert failed_notifications.status_code == 200

    critical_html = critical.get_data(as_text=True)
    unassigned_html = unassigned.get_data(as_text=True)
    stale_html = stale.get_data(as_text=True)

    assert _workspace_kpi_value(workspace_html, "Situations critiques") == _case_row_count(
        critical_html
    )
    assert _workspace_kpi_value(workspace_html, "Demandes non assignées") == _case_row_count(
        unassigned_html
    )
    assert _workspace_kpi_value(workspace_html, "Cas sans action") == _case_row_count(
        stale_html
    )
    assert "ops-kpi-resolved-decoy" not in critical_html
    assert "ops-kpi-resolved-decoy" not in unassigned_html
    assert "ops-kpi-resolved-decoy" not in stale_html
    assert "Filtres actifs" in critical_html
    assert "Risque: Critique" in critical_html
    assert "Responsable: non attribue" in unassigned_html
    assert "Cas sans action 72h" in stale_html
    assert workspace_html.count('/ops/cases?risk=critical') >= 2


def test_structure_scoped_admin_requests_excludes_other_structures(client, session):
    structure = _make_structure(session, structure_id=2, name="Structure 2", slug="structure-2")
    _make_structure(session, structure_id=3, name="Structure 3", slug="structure-3")
    user = _make_user(session, username="scoped_seed_user", email="scoped_seed_user@test.local")
    scoped_admin = _make_admin(
        session,
        username="scoped_admin_visibility",
        email="scoped_admin_visibility@test.local",
        role="admin",
        structure_id=structure.id,
    )
    _login_admin(client, scoped_admin)
    _satisfy_privileged_mfa(client, session, scoped_admin)

    in_scope = _make_request(
        session,
        title="scoped-visible-request",
        user_id=user.id,
        structure_id=structure.id,
        status="pending",
    )
    out_of_scope = _make_request(
        session,
        title="scoped-hidden-request",
        user_id=user.id,
        structure_id=3,
        status="pending",
    )

    resp = client.get("/admin/requests", follow_redirects=False)

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "scoped-visible-request" in html
    assert "scoped-hidden-request" not in html
