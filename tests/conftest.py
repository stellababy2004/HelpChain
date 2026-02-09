import pytest
import requests


# Block all requests to localhost/127.0.0.1 during tests (priority #1)
@pytest.fixture(autouse=True)
def _block_requests_to_localhost(monkeypatch):
    real_request = requests.sessions.Session.request

    def guarded(self, method, url, *args, **kwargs):
        if isinstance(url, str) and ("localhost" in url or "127.0.0.1" in url):
            raise RuntimeError(
                f"Blocked external HTTP call during tests: {method} {url}"
            )
        return real_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", guarded)


import pytest


# Canonical fixture for authenticated volunteer client
@pytest.fixture
def authenticated_volunteer_client(real_app, test_volunteer):
    client = real_app.test_client()
    client.get("/")
    with client.session_transaction() as sess:
        sess["volunteer_logged_in"] = True
        sess["volunteer_id"] = test_volunteer.id
    return client


"""
Early canonicalization guard: attempt to ensure the top-level name `extensions`
resolves to the package-qualified `backend.extensions` module before any other
imports run. This is deliberately placed at the very top of the file so pytest
collect/other modules won't create a separate top-level `extensions` module
that would result in a second SQLAlchemy() instance.
"""

import sys

try:
    # Try to prefer an already-imported package-qualified module
    if "backend.extensions" in sys.modules:
        sys.modules["extensions"] = sys.modules["backend.extensions"]
    else:
        # Try importing the canonical module and aliasing it immediately
        import importlib

        try:
            _tmp = importlib.import_module("backend.extensions")
            sys.modules["extensions"] = _tmp
        except Exception:
            # best-effort; continue if import fails
            pass
        # Defensive reconciliation: ensure any top-level 'extensions' module
        # references the canonical db instance before per-test create_all()
        try:
            try:
                canonical_ext = importlib.import_module("backend.extensions")
            except Exception:
                canonical_ext = None
            if canonical_ext is not None and "extensions" in sys.modules:
                dup = sys.modules.get("extensions")
                if dup is not None and dup is not canonical_ext:
                    try:
                        # Align attributes so the short-name module uses the
                        # canonical SQLAlchemy instance and related helpers.
                        for attr in ("db", "babel", "mail", "cache"):
                            try:
                                if hasattr(canonical_ext, attr):
                                    setattr(dup, attr, getattr(canonical_ext, attr))
                            except Exception:
                                pass
                        sys.modules["extensions"] = canonical_ext
                    except Exception:
                        pass
        except Exception:
            pass
except Exception:
    pass

import importlib

import pytest
from backend.helpchain_backend.src.app import create_app
from backend.extensions import db

print(
    f"[DB DIAG] conftest.py: id(db)={id(db)}, db.__module__={getattr(db, '__module__', None)}"
)
print(
    f"[DB DIAG] conftest.py: id(db)={id(db)}, db.__module__={getattr(db, '__module__', None)}"
)

# Diagnostics: Ensure only one app and one db instance
_app_instance = None
_db_instance = None


import pytest
from backend.helpchain_backend.src.app import create_app
from backend.extensions import db


@pytest.fixture(scope="function")
def real_app():
    from backend.helpchain_backend.src.app import create_app

    app = create_app({"TESTING": True})
    app.config.setdefault("SECRET_KEY", "test-secret-key")
    # Маркер за fail-fast: каноничен app factory ли е?
    assert app.config.get("APP_FACTORY_MARKER") == "CANONICAL_helpchain_backend_src_app"
    with app.app_context():
        from backend.extensions import db

        db.create_all()
        # --- ROUTE DIAGNOSTICS ---
        print(
            "[ROUTE CHECK] /achievements exists?:",
            any(r.rule == "/achievements" for r in app.url_map.iter_rules()),
        )
        for r in app.url_map.iter_rules():
            if "achiev" in r.rule:
                print("[ROUTE]", r.rule, "->", r.endpoint)
        # --- END DIAGNOSTICS ---
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def client(real_app):
    print(f"[TEST DIAG] session_interface type: {type(real_app.session_interface)}")
    return real_app.test_client(use_cookies=True)


@pytest.fixture(scope="function")
def db_session(real_app):
    from backend.extensions import db

    with real_app.app_context():
        yield db.session
        db.session.rollback()


# --- Fix #3B: Seed users ---
import datetime
from backend.models import Volunteer, AdminUser, User


@pytest.fixture(scope="function")
def seed_volunteer(db_session):
    volunteer = Volunteer(
        name="Test Volunteer",
        email="vol@test.bg",
        is_active=True,
        created_at=datetime.datetime.utcnow(),
    )
    db_session.add(volunteer)
    db_session.commit()
    return volunteer


@pytest.fixture(scope="function")
def seed_admin(db_session):
    admin = AdminUser(
        username="admin",
        email="admin@test.bg",
        password_hash="pbkdf2:sha256:260000$test$testhash",  # use a real hash in prod
        is_active=True,
        two_factor_enabled=False,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


# --- Fix #3C: Login helpers ---
@pytest.fixture(scope="function")
def login_volunteer(client, seed_volunteer):
    client.post(
        "/volunteer_login", data={"email": seed_volunteer.email}, follow_redirects=True
    )
    return client


@pytest.fixture(scope="function")
def login_admin(client, seed_admin):
    client.post(
        "/admin/login",
        data={"email": seed_admin.email, "password": "test"},
        follow_redirects=True,
    )
    return client


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


# Simple external admin stub server for tests that POST to 127.0.0.1:3000.
# This avoids ConnectionRefused errors from tests expecting an external admin
# service. It is lightweight and only used during pytest session runs.
@pytest.fixture(scope="session", autouse=True)
def external_admin_stub():
    """Start a tiny HTTP server on 127.0.0.1:3000 to respond to admin login calls."""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        import socket
        import time

        class _StubHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/admin_login":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                if self.path == "/admin_login":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                # suppress default logging to keep test output clean
                return

        class _ReusableHTTPServer(HTTPServer):
            allow_reuse_address = True

        # Try a couple of binding strategies to be robust on Windows CI
        server = None
        thread = None
        bind_addrs = [("127.0.0.1", 3000), ("0.0.0.0", 3000)]
        for addr in bind_addrs:
            try:
                server = _ReusableHTTPServer((addr[0], addr[1]), _StubHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                # Wait briefly and verify the server is accepting connections
                ready = False
                for _ in range(8):
                    try:
                        with socket.create_connection(("127.0.0.1", 3000), timeout=0.2):
                            ready = True
                            break
                    except Exception:
                        time.sleep(0.05)
                if ready:
                    break
                # if not ready, shut down and try next addr
                try:
                    server.shutdown()
                    server.server_close()
                except Exception:
                    pass
                server = None
                thread = None
            except OSError:
                server = None
                thread = None
                continue
    except Exception:
        # If we cannot bind the port (already in use or unavailable), continue
        # tests; they will report connection errors if the stub isn't present.
        server = None
        thread = None

    try:
        yield
    finally:
        try:
            if server is not None:
                server.shutdown()
                server.server_close()
        except Exception:
            pass
        try:
            if thread is not None and thread.is_alive():
                thread.join(timeout=1)
        except Exception:
            pass


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
    # If a non-canonical `extensions` module was already imported and it
    # exposes its own SQLAlchemy() instance, try to move any Table objects
    # into the canonical metadata before overwriting sys.modules so that
    # pre-imported mapped classes don't get lost or remain bound to a
    # different MetaData object.
    existing = sys.modules.get("extensions")
    try:
        canonical_db = getattr(_canonical_ext, "db", None)
    except Exception:
        canonical_db = None

    if existing is not None and existing is not _canonical_ext:
        try:
            existing_db = getattr(existing, "db", None)
        except Exception:
            existing_db = None
        # If the existing module had a SQLAlchemy() instance separate from
        # the canonical one, attempt to relocate its Table objects so
        # db.create_all() will see them. This is best-effort and only
        # performed during tests to avoid changing production behaviour.
        if (
            existing_db is not None
            and canonical_db is not None
            and id(getattr(existing_db, "metadata", None))
            != id(getattr(canonical_db, "metadata", None))
        ):
            try:
                # Move each table into the canonical metadata if missing
                for tbl in list(getattr(existing_db, "metadata", {}).tables.values()):
                    if (
                        getattr(tbl, "name", None)
                        not in getattr(canonical_db, "metadata", {}).tables
                    ):
                        try:
                            tbl.tometadata(canonical_db.metadata)
                        except Exception:
                            # ignore per-table failures
                            pass
            except Exception:
                pass

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

    # Reconcile any duplicate 'extensions' module objects by ensuring the
    # short-name module points to the canonical module and shares its
    # SQLAlchemy() instance. This is defensive: some import paths may have
    # loaded 'extensions' under a second module object earlier; make sure
    # its attributes reference the canonical db so tests see a single
    # SQLAlchemy instance.
    try:
        canonical_ext = importlib.import_module("backend.extensions")
        if (
            "extensions" in sys.modules
            and sys.modules["extensions"] is not canonical_ext
        ):
            try:
                dup = sys.modules["extensions"]
                # Copy over important extension attributes when present
                for attr in ("db", "babel", "mail", "cache"):
                    try:
                        if hasattr(canonical_ext, attr):
                            setattr(dup, attr, getattr(canonical_ext, attr))
                    except Exception:
                        pass
                # Finally, replace the entry so future imports get canonical module
                sys.modules["extensions"] = canonical_ext
            except Exception:
                pass
    except Exception:
        pass

# Collection-time best-effort: if we can locate a Declarative `Base` and a
# test DB path, create the schema in the file-backed SQLite DB so tests that
# execute queries at import/collection time (legacy tests) won't fail with
# "no such table/column". This is intentionally best-effort and only runs
# during pytest collection in the test runner environment.
try:
    import os
    import importlib

    db_path = os.environ.get("HELPCHAIN_TEST_DB_PATH")
    if db_path:
        bm = importlib.import_module("backend.models")
        Base = getattr(bm, "Base", None)
        if Base is not None:
            from sqlalchemy import create_engine

            engine = create_engine(f"sqlite:///{db_path}")
            try:
                Base.metadata.create_all(bind=engine)
            except Exception:
                pass
except Exception:
    # Non-fatal: continue collection even if schema creation fails here.
    pass

# Also attempt to create schema on any already-configured Flask-SQLAlchemy
# `db` object (best-effort). Some test imports bind models to that db and
# perform queries during collection; creating tables on its engine avoids
# "no such column" errors.
try:
    import importlib

    be_ext = importlib.import_module("backend.extensions")
    _db = getattr(be_ext, "db", None)
    if _db is not None:
        try:
            _db.create_all()
        except Exception:
            # Try to create tables with the models' Base against the db engine
            try:
                engine = getattr(_db, "engine", None)
                if engine is None and hasattr(_db, "get_engine"):
                    try:
                        engine = _db.get_engine()
                    except Exception:
                        engine = None
                if engine is not None:
                    bm = importlib.import_module("backend.models")
                    Base = getattr(bm, "Base", None)
                    if Base is not None:
                        Base.metadata.create_all(bind=engine)
            except Exception:
                pass
except Exception:
    pass


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

    # Create a unique email per test run to avoid UNIQUE constraint issues
    import uuid

    unique_email = f"admin+{uuid.uuid4().hex[:8]}@test.com"

    # Ensure idempotence for the canonical address if present (best-effort)
    try:
        existing = db_session.query(AdminUser).filter_by(email=unique_email).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
    except Exception:
        pass

    unique_username = f"test_admin_{uuid.uuid4().hex[:8]}"
    admin = AdminUser(username=unique_username, email=unique_email)
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
def authenticated_admin_client(real_app, test_admin_user):
    """Create a test client with authenticated admin user."""
    from flask_login import login_user

    admin_client = real_app.test_client()
    # Ensure bypass is set early so any setup requests from the fixture
    # are allowed to bypass the admin auth decorator and persist session.
    try:
        real_app.config["BYPASS_ADMIN_AUTH"] = True
    except Exception:
        pass
    # When testing, disable analytics hooks/views that may be None or unavailable
    # so admin views do not error during tests. This is a safe test-only toggle.
    try:
        if real_app.config.get("TESTING"):
            real_app.config.setdefault("ANALYTICS_DISABLED", True)
    except Exception:
        pass
    # Set legacy session flags (used by some code paths) and Flask-Login
    # session keys so protected admin routes recognize the user.
    with admin_client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = test_admin_user.id
        sess["admin_username"] = test_admin_user.username
        # Flask-Login stores the user id under a private key (commonly
        # '_user_id') and marks the session fresh with '_fresh'. Populate
        # these so `current_user` will be resolved on request handling.
        try:
            sess["_user_id"] = str(test_admin_user.id)
            sess["_fresh"] = True
            # Mark session modified so the test client persists the cookie
            try:
                sess.modified = True
            except Exception:
                try:
                    sess["modified"] = True
                except Exception:
                    pass
        except Exception:
            pass

    # Also attempt to call login_user() inside a request context so
    # `flask_login.current_user` is populated for the current test
    # process. This is best-effort and will not raise on failure.
    try:
        with app.test_request_context():
            try:
                login_user(test_admin_user)
            except Exception:
                pass
    except Exception:
        pass

    # Ensure test client sends Bulgarian Accept-Language by default so
    # flashed messages and localized templates render in tests expecting bg.
    try:
        admin_client.environ_base["HTTP_ACCEPT_LANGUAGE"] = "bg"
    except Exception:
        try:
            admin_client.environ_base.update({"HTTP_ACCEPT_LANGUAGE": "bg"})
        except Exception:
            pass
    # Test-only header to signal server-side bypass for admin auth when
    # running under pytest. This complements session-based approaches and
    # helps environments where cookies may not persist reliably.
    try:
        admin_client.environ_base["HTTP_X_ADMIN_BYPASS"] = "1"
    except Exception:
        try:
            admin_client.environ_base.update({"HTTP_X_ADMIN_BYPASS": "1"})
        except Exception:
            pass

    # Make a lightweight request to the debug session endpoint so the
    # server-side session is fully established and the client cookie is
    # persisted; this helps when tests inspect redirects/flash messages.
    try:
        admin_client.get("/_admin_session")
    except Exception:
        pass

    # Call debug endpoint that forces an admin login on the server side
    # (if implemented). This is a robust way to ensure the test client
    # receives the session cookie and the server recognizes the user.
    try:
        admin_client.get("/_admin_force_login")
    except Exception:
        pass

    # Also call the pytest-specific force-login endpoint (preferred).
    try:
        admin_client.get("/_pytest_force_admin_login")
    except Exception:
        pass

    # BYPASS already set early above; keep here for backward compatibility
    # but do not change it again.

    # Try performing the real login flow using the test client. This is
    # preferred because it goes through the same view logic the app uses
    # in production. Fall back to the session-key approach if the POST
    # isn't available for some reason (some legacy routes only expose GET).
    try:
        resp = admin_client.post(
            "/admin/login",
            data={"username": test_admin_user.username, "password": "TestPass123"},
            follow_redirects=True,
        )
        # Accept 200 or 302 as successful interactive login flows
        if resp is not None and resp.status_code in (200, 302):
            # Ensure the client cookie is persisted by making a lightweight
            # follow-up request to an always-available route. This avoids
            # reliance on debug endpoints that may not be registered.
            try:
                admin_client.get("/", follow_redirects=True)
            except Exception:
                try:
                    admin_client.get("/_health", follow_redirects=True)
                except Exception:
                    pass
            return admin_client
    except Exception:
        pass
    # As a last step, attempt a simple GET to the app root to ensure the
    # session cookie (if any) is persisted for the test client.
    try:
        admin_client.get("/", follow_redirects=True)
    except Exception:
        pass

    return admin_client


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
    # Use unique username and email for this seeded admin so repeated
    # test runs against a persistent file DB don't collide on UNIQUE
    # constraints. This matches the approach used for `test_admin_user`.
    import uuid

    unique_admin2fa_email = f"admin2fa+{uuid.uuid4().hex[:8]}@test.com"
    unique_admin2fa_username = f"test_admin_2fa_{uuid.uuid4().hex[:8]}"

    admin_with_2fa = AdminUser(
        username=unique_admin2fa_username,
        email=unique_admin2fa_email,
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
