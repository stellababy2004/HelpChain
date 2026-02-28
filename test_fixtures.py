import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    monkeypatch.setenv("HC_ENV", "test")
    monkeypatch.setenv("HELPCHAIN_TESTING", "1")
    monkeypatch.setenv("HC_DEFAULT_STRUCTURE_SLUG", "default")


@pytest.fixture
def app():
    from backend.helpchain_backend.src.app import create_app

    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    # create_app loads config objects after dict update; force test-only overrides here.
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["ALLOW_DEFAULT_TENANT_FALLBACK"] = True
    app.config["VOLUNTEER_DEV_BYPASS_ENABLED"] = True
    app.config["VOLUNTEER_DEV_BYPASS_EMAIL"] = "volunteer@test.local"
    yield app


@pytest.fixture
def db_schema(app):
    with app.app_context():
        from backend.models import db
        import backend.models  # noqa: F401
        import backend.models_with_analytics  # noqa: F401

        db.create_all()

        from backend.models import Structure

        if not Structure.query.filter_by(slug="default").first():
            db.session.add(Structure(name="Default", slug="default"))
            db.session.commit()

        yield

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app, db_schema):
    return app.test_client()


@pytest.fixture
def session(app, db_schema):
    """Legacy fixture: SQLAlchemy session handle."""
    from backend.models import db

    return db.session


@pytest.fixture
def db_session(session):
    """Compatibility alias used by parts of the test suite."""
    return session


@pytest.fixture
def real_app(app, db_schema):
    """Legacy alias fixture."""
    return app


@pytest.fixture
def init_test_data(app, session, db_schema):
    """
    Legacy + integration fixture.
    Returns common seeded entities under stable keys.
    """
    data = {}
    from backend.models import Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    if not structure:
        structure = Structure(name="Default", slug="default")
        session.add(structure)
        session.commit()
    data["structure"] = structure

    volunteer = None
    try:
        from backend.models import Volunteer

        volunteer = session.query(Volunteer).filter_by(email="volunteer@test.local").first()
        if not volunteer:
            volunteer = Volunteer(email="volunteer@test.local", name="Test Volunteer")
            if hasattr(volunteer, "structure_id"):
                volunteer.structure_id = getattr(structure, "id", None)
            session.add(volunteer)
            session.commit()
    except Exception:
        volunteer = None

    if volunteer is None:
        try:
            from backend.models import User

            volunteer = session.query(User).filter_by(email="volunteer@test.local").first()
            if not volunteer:
                volunteer = User(
                    username="volunteer_test_user",
                    email="volunteer@test.local",
                    password_hash="x",
                    role="volunteer",
                    is_active=True,
                )
                if hasattr(volunteer, "structure_id"):
                    volunteer.structure_id = getattr(structure, "id", None)
                session.add(volunteer)
                session.commit()
        except Exception:
            volunteer = {"id": 1, "email": "volunteer@test.local", "role": "volunteer"}

    data["volunteer"] = volunteer
    admin_with_2fa = None
    try:
        from werkzeug.security import generate_password_hash

        from backend.models import AdminUser

        admin_with_2fa = (
            session.query(AdminUser).filter_by(username="admin_2fa_test").first()
        )
        if not admin_with_2fa:
            admin_with_2fa = AdminUser(
                username="admin_2fa_test",
                email="admin_2fa_test@helpchain.local",
                password_hash=generate_password_hash("TestPass123"),
                role="admin",
                is_active=True,
            )
            session.add(admin_with_2fa)
            session.commit()
    except Exception:
        admin_with_2fa = None

    data["admin_with_2fa"] = admin_with_2fa
    return data


@pytest.fixture
def authenticated_volunteer_client(app, session, init_test_data):
    """Legacy fixture: test client with volunteer-like authenticated session."""
    client = app.test_client()
    volunteer = init_test_data.get("volunteer")
    vid = int(getattr(volunteer, "id", 1) or 1)

    with client.session_transaction() as s:
        s["volunteer_id"] = vid
        s["volunteer_logged_in"] = True
        s["_user_id"] = str(vid)
        s["user_id"] = vid
        s["role"] = "volunteer"
        s["is_authenticated"] = True

    return client


@pytest.fixture
def authenticated_admin_client(app, session, init_test_data, db_schema):
    """
    Legacy fixture: returns a client authenticated as an admin.
    """
    client = app.test_client()
    admin_id = None
    try:
        from backend.models import AdminUser

        admin = session.query(AdminUser).filter_by(email="admin@test.local").first()
        if not admin:
            admin = AdminUser(
                username="admin_test_user",
                email="admin@test.local",
                password_hash="x",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            session.commit()
        admin_id = getattr(admin, "id", None)
    except Exception:
        admin_id = 1

    with client.session_transaction() as s:
        s["_user_id"] = str(admin_id)
        s["user_id"] = admin_id
        s["role"] = "admin"
        s["is_authenticated"] = True
        s["is_admin"] = True
        s["admin_logged_in"] = True
        s["admin_id"] = admin_id

    return client


@pytest.fixture
def mock_ai_service(monkeypatch):
    async def _generate_response(message, context=None):
        return {
            "response": "Тестов отговор от AI",
            "confidence": 0.95,
            "provider": "mock-provider",
        }

    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.api.ai_service.generate_response",
        _generate_response,
    )
    return True


@pytest.fixture
def mock_smtp(mocker):
    """Legacy fixture expected by route tests."""
    try:
        return mocker.patch("backend.appy.mail.send")
    except Exception:
        return mocker.MagicMock()


@pytest.fixture
def test_volunteer(session):
    from backend.models import Volunteer

    volunteer = session.query(Volunteer).filter_by(email="dupe@test.local").first()
    if not volunteer:
        volunteer = Volunteer(
            name="Existing Volunteer",
            email="dupe@test.local",
            phone="+359888000000",
            location="Sofia",
        )
        session.add(volunteer)
        session.commit()
    return volunteer


@pytest.fixture
def test_admin_user(session):
    from backend.models import AdminUser
    from werkzeug.security import generate_password_hash

    admin = session.query(AdminUser).filter_by(username="security_admin").first()
    if not admin:
        admin = AdminUser(
            username="security_admin",
            email="security_admin@test.local",
            password_hash=generate_password_hash("SecurePass123"),
            role="admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()
    return admin
