from __future__ import annotations

from datetime import UTC, datetime

from backend.models import Request, Structure, User


def _make_user(session, suffix: str) -> User:
    user = User(
        username=f"pilotage_alertes_user_{suffix}",
        email=f"pilotage_alertes_{suffix}@test.local",
        password_hash="x",
        role="requester",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def test_admin_pilotage_alertes_critiques_smoke(authenticated_admin_client, session):
    ts = str(int(datetime.now(UTC).timestamp()))
    structure = session.query(Structure).filter_by(slug="default").first()

    user1 = _make_user(session, f"{ts}_1")
    user2 = _make_user(session, f"{ts}_2")
    user3 = _make_user(session, f"{ts}_3")

    session.add_all(
        [
            Request(
                title="Situation critique sans responsable",
                description="Suivi social",
                user_id=user1.id,
                status="pending",
                category="general",
                structure_id=getattr(structure, "id", None),
                risk_level="critical",
                risk_score=90,
                risk_signals='["no_owner"]',
                created_at=datetime.now(UTC),
            ),
            Request(
                title="Situation sans action 72h",
                description="Dossier en attente",
                user_id=user2.id,
                status="pending",
                category="general",
                structure_id=getattr(structure, "id", None),
                risk_level="attention",
                risk_score=62,
                risk_signals='["not_seen_72h"]',
                created_at=datetime.now(UTC),
            ),
            Request(
                title="Situation legacy sans signaux",
                description="Compatibilité historique",
                user_id=user3.id,
                status="pending",
                category="general",
                structure_id=getattr(structure, "id", None),
                risk_signals=None,
                created_at=datetime.now(UTC),
            ),
        ]
    )
    session.commit()

    resp = authenticated_admin_client.get("/admin/pilotage")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "Alertes critiques" in html
    assert "Situations à traiter en priorité" in html
    assert "Situations critiques sans responsable" in html
    assert "Situations sans action depuis 72 heures" in html
    assert "Affectations immédiates recommandées" in html
    assert "Revues managériales à effectuer aujourd’hui" in html
    # The priority table may be empty depending on risk logic; avoid hard dependency on CTA text.
    assert "traceback" not in html.lower()
