"""Organization logo upload, persistence and tenant-isolation regression tests."""

from io import BytesIO

from PIL import Image
from flask import g

from backend.models import OrganizationLogo, Structure, db
from tests.test_admin_team import _admin, _login


def _switch_admin(client, app, admin):
    # The shared app context in test_fixtures.py retains Flask g across requests.
    for key in ("_current_admin_actor", "_session_admin_actor", "_bearer_admin_actor"):
        g.pop(key, None)
    _switch_admin(client, app, admin)


def _png():
    buffer = BytesIO()
    Image.new("RGB", (48, 32), "blue").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_organization_logo_lifecycle_and_tenant_isolation(client, app):
    first = Structure(name="Logo Tenant A", slug="logo-tenant-a", status="active")
    second = Structure(name="Logo Tenant B", slug="logo-tenant-b", status="active")
    db.session.add_all([first, second])
    db.session.flush()
    admin_a = _admin("logo_admin_a", first.id)
    admin_b = _admin("logo_admin_b", second.id)
    db.session.commit()

    _switch_admin(client, app, admin_a)
    uploaded = client.post(
        "/admin/team/logo",
        data={"logo": (_png(), "logo.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 303
    stored = db.session.get(OrganizationLogo, first.id)
    assert stored is not None
    assert stored.png_data[:4] == bytes((137, 80, 78, 71))
    assert db.session.get(OrganizationLogo, second.id) is None

    own_logo = client.get("/admin/team/logo.png")
    assert own_logo.status_code == 200
    assert own_logo.headers["Content-Type"].startswith("image/png")
    assert own_logo.headers["Cache-Control"] == "private, no-store"

    # Use a separate browser session: Flask-Login may cache current_user
    # in the active request context when a test reuses one client.
    other_client = app.test_client()
    _switch_admin(other_client, app, admin_b)
    assert other_client.get("/admin/team/logo.png").status_code == 404
    assert other_client.post("/admin/team/logo/delete").status_code == 303
    assert db.session.get(OrganizationLogo, first.id) is not None

    _switch_admin(client, app, admin_a)
    assert client.post("/admin/team/logo/delete").status_code == 303
    assert db.session.get(OrganizationLogo, first.id) is None


def test_rejects_invalid_logo_without_persisting(client, app):
    structure = Structure(name="Invalid Logo Tenant", slug="invalid-logo-tenant", status="active")
    db.session.add(structure)
    db.session.flush()
    admin = _admin("invalid_logo_admin", structure.id)
    db.session.commit()
    _switch_admin(client, app, admin)
    response = client.post(
        "/admin/team/logo",
        data={"logo": (BytesIO(b"<svg>not a PNG</svg>"), "logo.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert db.session.get(OrganizationLogo, structure.id) is None


def test_readonly_cannot_manage_organization_logo(client, app):
    structure = Structure(name="Read Only Logo Tenant", slug="readonly-logo-tenant", status="active")
    db.session.add(structure)
    db.session.flush()
    user = _admin("readonly_logo_user", structure.id, role="readonly")
    db.session.commit()
    _switch_admin(client, app, user)
    assert client.get("/admin/team/logo.png").status_code == 403
    assert client.post(
        "/admin/team/logo",
        data={"logo": (_png(), "logo.png")},
        content_type="multipart/form-data",
    ).status_code == 403
    assert client.post("/admin/team/logo/delete").status_code == 403
