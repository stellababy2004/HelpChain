from __future__ import annotations

from datetime import UTC, datetime

from backend.models import Request, Structure, User


def _make_user(session) -> User:
    user = User(
        username=f"pilotage_user_{int(datetime.now(UTC).timestamp())}",
        email=f"pilotage_{int(datetime.now(UTC).timestamp())}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def test_admin_pilotage_route_smoke(authenticated_admin_client, session):
    structure = session.query(Structure).filter_by(slug="default").first()
    user = _make_user(session)
    req = Request(
        title="Pilotage smoke request",
        description="urgent logement",
        user_id=user.id,
        status="pending",
        category="general",
        structure_id=getattr(structure, "id", None),
        created_at=datetime.now(UTC),
    )
    session.add(req)
    session.commit()

    resp = authenticated_admin_client.get("/admin/pilotage")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Pilotage des situations sociales" in html
    assert "Situations critiques" in html
    assert "traceback" not in html.lower()
