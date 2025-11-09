import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.pool import StaticPool

# NOTE: Avoid importing model modules at top-level here. Models must be imported
# against the canonical `db` instance which the app provides; importing them
# too early can bind them to a different SQLAlchemy() object.
#
# Early aliasing: ensure legacy short import names resolve to the canonical
# backend.* modules before other imports during test collection. This avoids
# accidental re-execution or instantiation of multiple SQLAlchemy() objects
# when modules import using legacy names like `import models` or
# `from models import X`.
try:
    import os, sys

    if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
        print("[EARLY ALIASING] attempting to alias legacy model module names")
    from importlib import import_module

    bm = import_module("backend.models")
    bma = import_module("backend.models_with_analytics")
    legacy_to_mod = {
        "models": bm,
        "models_with_analytics": bma,
        "src.models": bm,
        "backend.src.models": bm,
        "helpchain_backend.models": bm,
        "helpchain_backend.src.models": bm,
        "helpchain_backend.src.models_with_analytics": bma,
        "backend.models_with_analytics": bma,
    }
    for name, mod in legacy_to_mod.items():
        if name not in sys.modules:
            sys.modules[name] = mod
            if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                print(f'[EARLY ALIASING] sys.modules["{name}"] -> {mod}')
except Exception as _alias_exc:
    # don't fail collection if aliasing can't be applied; we'll surface later
    if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
        print("[EARLY ALIASING] failed:", _alias_exc)


# Ensure tests force test-mode early so app initialization picks it up.
# This must happen before importing `appy` so HELPCHAIN_TESTING influences
# the application's configuration (database selection, logging, etc.).
os.environ.setdefault("HELPCHAIN_TESTING", "1")
import tempfile

# Use a file-backed temporary SQLite DB for tests to avoid in-memory
# visibility and index/name-collision issues across multiple engine
# instances. A unique temp file per test session ensures a clean DB.
_tmp_db = tempfile.NamedTemporaryFile(
    delete=False, prefix="helpchain_test_", suffix=".db"
)
_tmp_db.close()
os.environ.setdefault("HELPCHAIN_TEST_DB_PATH", _tmp_db.name)

import pytest

# Добавяме helpchain-backend (родител на папката src) в началото на sys.path,
# за да може `import src` да работи
_root = os.path.dirname(__file__)
_src_parent = os.path.join(_root, "helpchain-backend")
if os.path.isdir(_src_parent):
    sys.path.insert(0, _src_parent)

# Добавя текущата папка (backend) в sys.path така че 'appy' да се импортира директно
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# BEST-EFFORT: ensure canonical extension/models modules are aliased immediately
# so other imports that use short names like `import models` or `from models import X`
# resolve to the same canonical modules and don't create duplicate mapped classes.
try:
    # alias backend.extensions -> extensions so imports using the short name
    # reference the same SQLAlchemy() instance used by the app.
    _canonical_ext = importlib.import_module("backend.extensions")
    for _alias in ("extensions", "backend.extensions"):
        sys.modules[_alias] = _canonical_ext
except Exception:
    # best-effort; if import fails, let subsequent fixtures handle it
    _canonical_ext = None

try:
    # alias common alternate model module names to the canonical backend.models
    _canonical_models = importlib.import_module("backend.models")
    for _m in (
        "models",
        "backend.models",
        "helpchain_backend.src.models",
        "helpchain_backend.src.models.audit",
    ):
        sys.modules[_m] = _canonical_models
except Exception:
    # if models aren't importable at this exact moment, it's fine; later
    # fixtures will import models and perform aliasing as needed.
    _canonical_models = None

# Lightweight canonicalization: ensure common import names point to the
# canonical backend modules. Avoid clearing mappers here to prevent
# accidentally removing mapped attributes — we only want import-time aliasing.
try:
    _be = importlib.import_module("backend.models")
    for _alias in ("models", "helpchain_backend.src.models"):
        sys.modules[_alias] = _be
except Exception:
    # If backend.models isn't importable at module-import time, the
    # session fixtures will perform aliasing later when it's safe.
    pass

# NOTE: Do NOT import models at top-level here. Importing models early binds them
# to whatever SQLAlchemy() instance is available at import time. We import
# models inside the session-scoped fixture below after aliasing the canonical
# `backend.extensions` module so models attach to the app's `db` instance.


@pytest.fixture(scope="session", autouse=True)
def setup_models():
    """Ensure models are imported against the canonical `db` instance.

    This fixture aliases the project's `backend.extensions` module (which
    contains the canonical Flask-SQLAlchemy instance) into sys.modules under
    common names before importing model modules. That prevents models from
    being bound to a different `db` object during import and ensures
    `db.metadata` is populated when tests run.
    """
    # Best-effort aliasing of canonical extensions module
    try:
        try:
            canonical_ext = importlib.import_module("backend.extensions")
        except Exception:
            canonical_ext = None
        if canonical_ext is not None:
            # Overwrite any existing aliases so models import against the
            # canonical db instance. This is deliberate: tests should use the
            # app-provided SQLAlchemy() instance, not one created earlier by a
            # different import path.
            for alias in ("extensions", "backend.extensions"):
                sys.modules[alias] = canonical_ext
    except Exception:
        # If aliasing fails, continue and let imports raise clearly later.
        canonical_ext = None

    # Import model modules so SQLAlchemy tables/register them with the
    # canonical db.metadata. Do not clear mappers here; instead ensure the
    # short import names map to the canonical module so duplicate imports
    # under alternate names don't occur.
    # Import a set of possible model modules so all table classes register
    # with SQLAlchemy metadata. Some layouts split models across multiple
    # modules (models_with_analytics, helpchain_backend.src.models, ...).
    for m in (
        "backend.models",
        "backend.models_with_analytics",
        "helpchain_backend.src.models",
        "models",
        "models_with_analytics",
    ):
        try:
            importlib.import_module(m)
        except ModuleNotFoundError:
            continue
        except Exception:
            # Let other import errors surface later to keep diagnostics clear
            continue
    # Ensure short import names point to the canonical module object
    try:
        _bm = importlib.import_module("backend.models")
        sys.modules.setdefault("models", _bm)
        sys.modules.setdefault("helpchain_backend.src.models", _bm)
    except Exception:
        pass

    # Extra diagnostic: enumerate AuditLog registrations early (before app import)
    try:
        if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
            print(
                "[TEST DEBUG] Early diagnostic: scanning registry and sys.modules for AuditLog entries"
            )
            try:
                be_ext = importlib.import_module("backend.extensions")
                reg = getattr(getattr(be_ext, "Model", None), "registry", None)
                print("[TEST DEBUG] registry object:", reg)
                if reg is not None:
                    found = []
                    for m in reg.mappers:
                        try:
                            cls = m.class_
                        except Exception:
                            continue
                        if getattr(cls, "__name__", None) == "AuditLog":
                            found.append(
                                (cls, getattr(cls, "__module__", None), id(cls))
                            )
                    if found:
                        print("[TEST DEBUG] AuditLog entries from registry:")
                        for cls, mod, cid in found:
                            modfile = getattr(sys.modules.get(mod), "__file__", None)
                            print(
                                f"[TEST DEBUG] registry -> class id={cid} module={mod} file={modfile} cls={cls!r}"
                            )
                    else:
                        print(
                            "[TEST DEBUG] No AuditLog entries found in registry at early stage"
                        )
            except Exception as _e:
                print(
                    "[TEST DEBUG] Could not inspect backend.extensions registry early:",
                    _e,
                )

            # Also scan sys.modules for any modules exposing AuditLog attribute
            exposed = []
            for modname, modobj in list(sys.modules.items()):
                if not modobj:
                    continue
                try:
                    attr = getattr(modobj, "AuditLog", None)
                except Exception:
                    continue
                if attr is None:
                    continue
                exposed.append(
                    (
                        modname,
                        getattr(attr, "__module__", None),
                        id(attr),
                        getattr(modobj, "__file__", None),
                    )
                )
            if exposed:
                print("[TEST DEBUG] Modules exposing AuditLog (early):")
                for modname, attrmod, objid, modfile in exposed:
                    print(
                        f"[TEST DEBUG] - sys.modules['{modname}'] (file={modfile}) exposes AuditLog -> attr module={attrmod} id={objid}"
                    )
            else:
                print(
                    "[TEST DEBUG] No modules expose an 'AuditLog' attribute at early stage"
                )
    except Exception:
        pass
    # Diagnostic: print what extension modules and db instances are present
    try:
        mods = [m for m in sys.modules.keys() if "extension" in m.lower()]
        print("[TEST DEBUG] setup_models: extension-like modules:", mods)
        try:
            be_ext = importlib.import_module("backend.extensions")
            print(
                "[TEST DEBUG] backend.extensions.db id:",
                id(getattr(be_ext, "db", None)),
            )
        except Exception:
            print("[TEST DEBUG] backend.extensions not importable during setup_models")
        try:
            plain_ext = importlib.import_module("extensions")
            print("[TEST DEBUG] extensions.db id:", id(getattr(plain_ext, "db", None)))
        except Exception:
            print("[TEST DEBUG] extensions not importable during setup_models")
        try:
            m = importlib.import_module("backend.models")
            Ach = getattr(m, "Achievement", None)
            print(
                "[TEST DEBUG] backend.models attrs sample:",
                [a for a in dir(m) if not a.startswith("__")][:40],
            )
            print("[TEST DEBUG] AdminUser in backend.models?:", hasattr(m, "AdminUser"))
            try:
                AdminUser = getattr(m, "AdminUser", None)
                print(
                    "[TEST DEBUG] AdminUser has __table__?:",
                    hasattr(AdminUser, "__table__"),
                )
                if hasattr(AdminUser, "__table__"):
                    try:
                        print(
                            "[TEST DEBUG] AdminUser.__table__.name:",
                            AdminUser.__table__.name,
                        )
                    except Exception as _e:
                        print("[TEST DEBUG] Could not read AdminUser.__table__:", _e)
            except Exception:
                pass
            try:
                be_ext = importlib.import_module("backend.extensions")
                print(
                    "[TEST DEBUG] backend.extensions.metadata tables:",
                    sorted(getattr(be_ext.db, "metadata").tables.keys()),
                )
            except Exception:
                pass
            if Ach is not None:
                try:
                    print(
                        "[TEST DEBUG] Achievement.__table__.name:", Ach.__table__.name
                    )
                except Exception as _e:
                    print("[TEST DEBUG] Could not read Achievement.__table__:", _e)
        except Exception as _e:
            print(
                "[TEST DEBUG] Could not import backend.models during setup_models:", _e
            )
    except Exception:
        pass


# Ensure canonical extensions `db` is available before any models import.
# This avoids duplicate SQLAlchemy() instances and missing metadata tables in tests.
import sys
import importlib

try:
    canonical_ext = importlib.import_module("backend.extensions")
except Exception:
    canonical_ext = None

if canonical_ext is not None:
    # Make sure legacy/relative import names resolve to the same module
    sys.modules.setdefault("extensions", canonical_ext)
    sys.modules.setdefault("backend.extensions", canonical_ext)

# Now import models so they bind to the canonical db
try:
    importlib.import_module("backend.models")
except ModuleNotFoundError:
    # fallback to legacy plain name if package path differs in some CI setups
    importlib.import_module("models")

# Optional: diagnostic print to CI logs to verify tables were registered
try:
    from backend.extensions import db

    print(
        "[TEST DEBUG] tables registered after importing models:",
        sorted(db.metadata.tables.keys()),
    )
except Exception as e:
    print("[TEST DEBUG] Could not print db.metadata after importing models:", e)


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    try:
        # Prefer the richer app variant (which registers the public index route)
        # when available. Fall back to the base `appy` module otherwise.
        try:
            from appy_with_analytics import app
        except Exception:
            from appy import app

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
        # Do not override the app's DB URI here. The application module
        # reads HELPCHAIN_TEST_DB_PATH (set by the tests) and configures
        # `app.config["SQLALCHEMY_DATABASE_URI"]` accordingly. Overriding
        # it here with an in-memory URI can create two different engines
        # and lead to "no such table" OperationalError at request time.
        # Keep engine options only if not already configured by the app.
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        if not app.config.get("SQLALCHEMY_ENGINE_OPTIONS"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        # Ensure admin authentication is enforced during tests by default.
        # Tests that need to bypass admin auth for public routes may override
        # this by setting `app.config['BYPASS_ADMIN_AUTH'] = True` explicitly.
        app.config["BYPASS_ADMIN_AUTH"] = False

        # Ensure the application's database schema exists for tests that
        # don't explicitly request a DB session fixture. This prevents
        # OperationalError in endpoints that query tables like admin_users.
        try:
            with app.app_context():
                try:
                    from backend.extensions import db as _db

                    _db.create_all()
                except Exception:
                    # best-effort: if schema creation isn't possible here,
                    # let tests that depend on DB use the db_session fixture.
                    pass
        except Exception:
            pass
        return app
    except ImportError:
        # Fallback if appy import fails
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test_key"
        return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Create a database session for testing."""
    from appy import _ensure_db_engine_registration, db

    # Ensure the canonical extensions module is aliased so model imports use
    # the same SQLAlchemy() instance that the app provides. This prevents
    # models from being bound to a different `db` object and ensures
    # `db.create_all()` will create the expected tables.
    try:
        try:
            canonical_ext = importlib.import_module("backend.extensions")
        except Exception:
            canonical_ext = None
        if canonical_ext is not None:
            for alias in ("extensions", "backend.extensions"):
                if alias not in sys.modules:
                    sys.modules[alias] = canonical_ext

    except Exception:
        # best-effort; fall through to normal imports
        pass

    # Import models to ensure SQLAlchemy is aware of all tables before create_all()
    try:
        importlib.import_module("backend.models")
    except ModuleNotFoundError:  # pragma: no cover - fallback when package path differs
        importlib.import_module("models")

    # Lightweight aliasing to ensure short import names resolve to the
    # canonical backend.models module. Avoid clearing mappers here.
    try:
        _bm = importlib.import_module("backend.models")
        sys.modules.setdefault("models", _bm)
        sys.modules.setdefault("helpchain_backend.src.models", _bm)
    except Exception:
        pass

    # Ensure mappers are configured after importing models so relationships
    # are resolved before any instances or relationship accesses occur.
    try:
        from sqlalchemy.orm import configure_mappers

        try:
            configure_mappers()
        except Exception:
            # If configure_mappers fails, we'll let subsequent code fail in a
            # clearer place; continue for now.
            pass
    except Exception:
        pass

    try:
        GamificationService = getattr(
            importlib.import_module("backend.gamification_service"),
            "GamificationService",
        )
    except ModuleNotFoundError:  # pragma: no cover - fallback
        GamificationService = getattr(
            importlib.import_module("gamification_service"),
            "GamificationService",
        )

    with app.app_context():
        _ensure_db_engine_registration()
        # Debug: print metadata before create_all to help CI diagnostics
        try:
            print(
                "[TEST DEBUG] SQLAlchemy metadata tables before create_all:",
                sorted(db.metadata.tables.keys()),
            )
        except Exception as _err:
            print("[TEST DEBUG] Could not list metadata before create_all:", _err)
        # Extra diagnostic: check whether AdminUser.__table__ is bound to the
        # same MetaData object as the app's db.metadata. This helps detect
        # models imported against a different SQLAlchemy instance.
        try:
            if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                try:
                    from backend.models import AdminUser  # type: ignore

                    admin_tbl = getattr(AdminUser, "__table__", None)
                    if admin_tbl is not None:
                        print(
                            "[TEST DEBUG] AdminUser.__table__.metadata is db.metadata?:",
                            id(getattr(admin_tbl, "metadata", None)) == id(db.metadata),
                        )
                        print(
                            "[TEST DEBUG] id(db.metadata):",
                            id(db.metadata),
                            "id(AdminUser.__table__.metadata):",
                            id(getattr(admin_tbl, "metadata", None)),
                        )
                        try:
                            print(
                                "[TEST DEBUG] AdminUser metadata tables:",
                                sorted(
                                    [
                                        t.name
                                        for t in getattr(
                                            admin_tbl, "metadata"
                                        ).tables.keys()
                                    ]
                                ),
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

                # If some mapped classes are bound to a different MetaData object
                # (common when a shim module created its own SQLAlchemy instance),
                # attempt to move their Table objects into the canonical app
                # metadata so db.create_all() can see all referenced tables.
                try:
                    if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                        # Collect candidate Table objects from loaded model classes
                        other_tables = []
                        for mod in list(sys.modules.values()):
                            if not mod:
                                continue
                            try:
                                for attr_name in dir(mod):
                                    try:
                                        attr = getattr(mod, attr_name)
                                    except Exception:
                                        continue
                                    if isinstance(attr, type) and hasattr(
                                        attr, "__table__"
                                    ):
                                        tbl = getattr(attr, "__table__", None)
                                        if tbl is None:
                                            continue
                                        # If the table's metadata is different, record it
                                        if id(getattr(tbl, "metadata", None)) != id(
                                            db.metadata
                                        ):
                                            other_tables.append(tbl)
                            except Exception:
                                continue
                        # Attempt to relocate each table into the canonical metadata
                        relocated = []
                        for tbl in other_tables:
                            try:
                                if tbl.name not in db.metadata.tables:
                                    tbl.tometadata(db.metadata)
                                    relocated.append(tbl.name)
                                    print(
                                        f"[TEST DEBUG] tometadata: moved table {tbl.name} into app db.metadata"
                                    )
                            except Exception as _e:
                                print(
                                    f"[TEST DEBUG] tometadata failed for {getattr(tbl, 'name', None)}: {_e}"
                                )
                        if relocated:
                            try:
                                print(
                                    "[TEST DEBUG] relocated tables into app metadata:",
                                    relocated,
                                )
                            except Exception:
                                pass
                        # Re-run mapper configuration after moving tables so relationships
                        # and ForeignKeys resolve against the canonical metadata.
                        try:
                            from sqlalchemy.orm import configure_mappers

                            try:
                                configure_mappers()
                                print(
                                    "[TEST DEBUG] configure_mappers() ran after tometadata"
                                )
                            except Exception as _e:
                                print(
                                    "[TEST DEBUG] configure_mappers() failed after tometadata:",
                                    _e,
                                )
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # Ensure a clean database state for the test session. In some cases the
        # in-memory engine or earlier imports may have already created tables or
        # indexes; drop them first to avoid „already exists" errors during
        # db.create_all(). This is safe in TESTING mode.
        try:
            print("[TEST DEBUG] Dropping existing tables (test setup)")
            db.drop_all()
        except Exception:
            pass

        try:
            db.create_all()
        except Exception as _e:
            # Some SQLite edge-cases may report existing indexes/tables during
            # repeated create attempts (especially if a previous import created
            # parts of the schema). If it's a benign "already exists" error,
            # print a debug line and continue; otherwise re-raise.
            msg = str(_e).lower()
            if "already exists" in msg or "index" in msg:
                print(
                    "[TEST DEBUG] db.create_all() raised, but looks benign (already exists):",
                    _e,
                )
            else:
                raise

        # Debug: print metadata after create_all so CI logs show which tables were created
        try:
            print(
                "[TEST DEBUG] SQLAlchemy metadata tables after create_all:",
                sorted(db.metadata.tables.keys()),
            )
        except Exception as _err:
            print("[TEST DEBUG] Could not list metadata after create_all:", _err)
        # Diagnostic: enumerate any loaded classes named 'AuditLog' to detect
        # duplicate model registrations coming from different module paths.
        try:
            found = []
            for mname, mod in list(sys.modules.items()):
                if not mod:
                    continue
                try:
                    for attr_name in dir(mod):
                        try:
                            attr = getattr(mod, attr_name)
                        except Exception:
                            continue
                        if (
                            isinstance(attr, type)
                            and getattr(attr, "__name__", None) == "AuditLog"
                        ):
                            found.append(
                                (
                                    mname,
                                    attr,
                                    id(attr),
                                    getattr(attr, "__module__", None),
                                )
                            )
                except Exception:
                    continue
            if found:
                print("[TEST DEBUG] Found AuditLog class definitions in modules:")
                for mname, cls, cid, modpath in found:
                    print(
                        "  module=",
                        mname,
                        "cls=",
                        cls,
                        "id=",
                        cid,
                        "__module__=",
                        modpath,
                    )
            else:
                print("[TEST DEBUG] No AuditLog class objects found in sys.modules")
        except Exception as _err:
            print("[TEST DEBUG] Could not enumerate AuditLog classes:", _err)
        # Diagnostic: inspect Achievement class to verify mapped attributes
        try:
            m = importlib.import_module("backend.models")
            Ach = getattr(m, "Achievement", None)
            print(
                "[TEST DEBUG] Achievement class:",
                Ach,
                "__module__:",
                getattr(Ach, "__module__", None),
            )
            print("[TEST DEBUG] hasattr(Achievement, 'id'):", hasattr(Ach, "id"))
            try:
                print(
                    "[TEST DEBUG] Achievement.id attr repr:",
                    repr(getattr(Ach, "id", None)),
                )
            except Exception as _e:
                print("[TEST DEBUG] Could not repr Achievement.id:", _e)
            # list some representative attributes
            try:
                attrs = [a for a in dir(Ach) if not a.startswith("__")][:40]
                print("[TEST DEBUG] Achievement attributes sample:", attrs)
            except Exception:
                pass
        except Exception as _err:
            print("[TEST DEBUG] Could not inspect Achievement class:", _err)

        # Ensure default achievements exist for gamification tests
        GamificationService.initialize_achievements()
        try:
            yield db.session
        finally:
            db.session.remove()
            db.drop_all()


@pytest.fixture
def mock_smtp():
    """Mock SMTP server for email testing."""
    with patch("flask_mail.Mail.send") as mock_send:
        mock_send.return_value = True
        yield mock_send


@pytest.fixture
def mock_analytics():
    """Mock analytics service for testing."""
    with patch("analytics_service.analytics_service") as mock_service:
        mock_service.track_event.return_value = True
        yield mock_service


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    mock_service = MagicMock()
    mock_service.generate_response.return_value = {
        "response": "Тестов отговор от AI",
        "confidence": 0.8,
        "provider": "mock",
    }
    mock_service.generate_response_sync.return_value = {
        "response": "Тестов отговор от AI",
        "confidence": 0.8,
        "provider": "mock",
    }
    mock_service.get_ai_status.return_value = {
        "status": "healthy",
        "providers": ["OpenAI GPT", "Google Gemini"],
        "active_provider": "mock",
    }

    # Patch at the app level where it's imported
    with patch("appy.ai_service", mock_service):
        yield mock_service


@pytest.fixture
def test_admin_user(db_session):
    """Create a test admin user."""
    try:
        from backend.models import AdminUser
    except ImportError:  # pragma: no cover - fallback when package path differs
        from backend.models import AdminUser  # type: ignore

    admin = AdminUser(username="test_admin", email="admin@test.com")
    admin.set_password("TestPass123")
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def test_volunteer(db_session):
    """Create a test volunteer."""
    try:
        from backend.models import Volunteer
    except ImportError:  # pragma: no cover - fallback when package path differs
        from backend.models import Volunteer  # type: ignore

    volunteer = Volunteer(
        name="Тестов Доброволец",
        email="volunteer@test.com",
        phone="+359888123456",
        location="София",
    )
    db_session.add(volunteer)
    db_session.commit()
    return volunteer


@pytest.fixture
def test_help_request(db_session, test_volunteer):
    """Create a test help request."""
    try:
        from backend.models import HelpRequest
    except ImportError:  # pragma: no cover - fallback when package path differs
        from backend.models import HelpRequest  # type: ignore

    request = HelpRequest(
        title="Тестова заявка за помощ",
        description="Това е тестова заявка за помощ",
        name="Тестов Потребител",
        email="user@test.com",
        message="Нуждая се от помощ с тестване",
        status="pending",
    )
    db_session.add(request)
    db_session.commit()
    return request


@pytest.fixture
def authenticated_admin_client(app, test_admin_user):
    """Create a test client with authenticated admin user."""
    admin_client = app.test_client()
    with app.test_request_context():
        with admin_client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_user_id"] = test_admin_user.id
            sess["admin_username"] = test_admin_user.username
    return admin_client


@pytest.fixture
def authenticated_volunteer_client(app, test_volunteer):
    """Create a test client with authenticated volunteer user."""
    volunteer_client = app.test_client()
    with app.test_request_context():
        with volunteer_client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = test_volunteer.id
            sess["volunteer_name"] = test_volunteer.name
    return volunteer_client


@pytest.fixture
def app_context(app):
    """Provide app context for tests that need it."""
    with app.app_context():
        yield


@pytest.fixture
def db_transaction(db_session):
    """Provide a database transaction that rolls back after test."""
    db_session.begin_nested()
    yield db_session
    db_session.rollback()


@pytest.fixture
def temp_upload_file(tmp_path):
    """Create a temporary file for upload testing."""
    file_path = tmp_path / "test_file.png"
    file_path.write_bytes(b"fake png content")
    return file_path


@pytest.fixture
def admin_credentials():
    """Get admin login credentials from environment."""
    return {"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "Admin123")}


@pytest.fixture
def login_admin(client, admin_credentials):
    """Helper to login as admin and return authenticated client."""
    response = client.post(
        "/admin/login", data=admin_credentials, follow_redirects=True
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def init_test_data(db_session, test_admin_user, test_volunteer, test_help_request):
    """Ensure commonly used objects exist for integration-style tests."""
    try:
        from backend.models import AdminUser, Volunteer
    except ImportError:  # pragma: no cover - fallback when package path differs
        from backend.models import AdminUser, Volunteer  # type: ignore

    # Create an admin account with enabled 2FA so tests can exercise that flow
    admin_with_2fa = AdminUser(
        username="test_admin_2fa",
        email="admin2fa@test.com",
    )
    admin_with_2fa.set_password("TestPass123")
    admin_with_2fa.enable_2fa()
    db_session.add(admin_with_2fa)

    # Extra volunteer with richer gamification stats for leaderboard-style checks
    extra_volunteer = Volunteer(
        name="Активен Доброволец",
        email="active_volunteer@test.com",
        phone="+359888654321",
        location="Пловдив",
        points=150,
        total_tasks_completed=3,
    )
    db_session.add(extra_volunteer)

    db_session.commit()

    return {
        "admin": test_admin_user,
        "admin_with_2fa": admin_with_2fa,
        "volunteer": test_volunteer,
        "extra_volunteer": extra_volunteer,
        "help_request": test_help_request,
    }
