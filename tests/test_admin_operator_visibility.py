from datetime import datetime, timedelta, UTC


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


def test_admin_requests_shows_seeded_requests_even_with_null_and_new_status(client, session):
    _make_structure(session, structure_id=2, name="Structure 2", slug="structure-2")
    _make_structure(session, structure_id=3, name="Structure 3", slug="structure-3")
    user = _make_user(session, username="seed_user", email="seed_user@test.local")
    admin = _make_admin(
        session,
        username="global_admin_visibility",
        email="global_admin_visibility@test.local",
        role="admin",
        structure_id=None,
    )
    _login_admin(client, admin)

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
