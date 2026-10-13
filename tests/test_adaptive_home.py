from pathlib import Path
from uuid import uuid4

from jinja2 import Environment

from backend.models import AdminUser, Structure

HOME_PATH = Path("templates/admin/admin_home.html")
HOME = HOME_PATH.read_text(encoding="utf-8")


def test_home_jinja_is_valid():
    Environment(autoescape=True).parse(HOME)


def test_core_requests_remain_available():
    assert "admin.admin_requests" in HOME


def test_notifications_are_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('notifications')"
    ) == 4
    assert "admin.admin_notifications_list" in HOME


def test_security_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('security')"
    ) == 4
    assert "admin.admin_security" in HOME


def test_platform_action_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('platform')"
    ) == 1
    assert "admin.admin_roles" in HOME


def test_pilotage_is_adaptive():
    assert HOME.count(
        "adaptive_module_enabled('pilotage')"
    ) == 2
    assert "admin.admin_risk_map" in HOME
    assert "admin.admin_professionals_map" in HOME


def test_global_admin_escape_hatch_exists():
    assert HOME.count("adaptive_global_admin") >= 9


def _render_home_for_organization(client, session, organization_type):
    suffix = uuid4().hex[:8]
    structure = Structure(
        name=f"Adaptive {suffix}",
        slug=f"adaptive-{suffix}",
        organization_type=organization_type,
    )
    session.add(structure)
    session.flush()
    admin = AdminUser(
        username=f"adaptive_admin_{suffix}",
        email=f"adaptive_admin_{suffix}@test.local",
        password_hash="x",
        role="admin",
        is_active=True,
        structure_id=structure.id,
    )
    session.add(admin)
    session.commit()

    with client.session_transaction() as browser_session:
        browser_session["_user_id"] = str(admin.id)
        browser_session["user_id"] = admin.id
        browser_session["admin_id"] = admin.id
        browser_session["role"] = admin.role
        browser_session["is_authenticated"] = True
        browser_session["is_admin"] = True
        browser_session["admin_logged_in"] = True

    response = client.get("/admin/home")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_generic_dashboard_profile_renders_for_unknown_organization(client, session):
    html = _render_home_for_organization(client, session, "unknown")

    assert "Pilotage administratif" in html
    assert "Centre de coordination admin" in html
    assert "Tableau de bord de l’établissement" not in html
    assert "Tableau de bord du CCAS" not in html


def test_school_dashboard_profile_renders_without_generic_intelligence(client, session):
    html = _render_home_for_organization(client, session, "school")

    assert "Pilotage de l’établissement" in html
    assert "Tableau de bord de l’établissement" in html
    assert "Suivez les demandes, identifiez les situations à traiter" in html
    assert "Centre de coordination admin" not in html
    assert "Ce qui demande une action" not in html


def test_ccas_dashboard_profile_renders_social_coordination(client, session):
    html = _render_home_for_organization(client, session, "ccas")

    assert "Coordination sociale" in html
    assert "Tableau de bord du CCAS" in html
    assert "Coordonnez les situations à traiter" in html
    assert "Situations à traiter" in html
    assert "Suivi des situations" in html
    assert "Centre de coordination admin" not in html
