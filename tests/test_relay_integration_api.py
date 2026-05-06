import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.pool import NullPool
from werkzeug.security import check_password_hash, generate_password_hash


DB_ROOT = Path(os.getcwd()) / ".tmp_test_dbs"
DB_PATH = DB_ROOT / "relay_test.sqlite"
ENV_KEYS = (
    "HC_ENV",
    "HELPCHAIN_TESTING",
    "HC_SKIP_SELFHEAL",
    "HC_DB_PATH",
    "DATABASE_URL",
    "SQLALCHEMY_DATABASE_URI",
    "TMPDIR",
    "TEMP",
    "TMP",
)


def _cleanup_sqlite_files(db_path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        try:
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        except Exception:
            pass


@pytest.fixture(scope="module")
def relay_env():
    DB_ROOT.mkdir(parents=True, exist_ok=True)
    _cleanup_sqlite_files(DB_PATH)

    original_env = {key: os.environ.get(key) for key in ENV_KEYS}
    db_uri = f"sqlite:///{DB_PATH.as_posix()}"

    os.environ["HC_ENV"] = "test"
    os.environ["HELPCHAIN_TESTING"] = "1"
    os.environ["HC_SKIP_SELFHEAL"] = "1"
    os.environ["HC_DB_PATH"] = str(DB_PATH)
    os.environ["DATABASE_URL"] = db_uri
    os.environ["SQLALCHEMY_DATABASE_URI"] = db_uri
    os.environ["TMPDIR"] = str(DB_ROOT)
    os.environ["TEMP"] = str(DB_ROOT)
    os.environ["TMP"] = str(DB_ROOT)

    try:
        yield {"db_path": DB_PATH, "db_uri": db_uri}
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _cleanup_sqlite_files(DB_PATH)


@pytest.fixture(scope="module")
def app(relay_env):
    from backend.helpchain_backend.src.app import create_app

    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": relay_env["db_uri"],
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"timeout": 5, "check_same_thread": False},
                "poolclass": NullPool,
            },
        }
    )
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["ALLOW_DEFAULT_TENANT_FALLBACK"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = relay_env["db_uri"]
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"timeout": 5, "check_same_thread": False},
        "poolclass": NullPool,
    }
    app.config["HC_TEST_DB_PATH"] = str(relay_env["db_path"])
    return app


@pytest.fixture
def db_schema(app, relay_env):
    from backend.models import Structure, db
    import backend.models  # noqa: F401
    import backend.models_with_analytics  # noqa: F401

    ctx = app.app_context()
    ctx.push()
    try:
        db.session.rollback()
        db.session.remove()
        db.engine.dispose()
        _cleanup_sqlite_files(relay_env["db_path"])
        db.metadata.create_all(bind=db.engine)

        if not Structure.query.filter_by(slug="default").first():
            db.session.add(Structure(name="Default", slug="default"))
            db.session.commit()

        yield
    finally:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            db.session.remove()
        except Exception:
            pass
        try:
            db.metadata.drop_all(bind=db.engine)
        except Exception:
            pass
        try:
            db.engine.dispose()
        except Exception:
            pass
        ctx.pop()
        _cleanup_sqlite_files(relay_env["db_path"])


@pytest.fixture
def client(app, db_schema):
    return app.test_client()


@pytest.fixture
def session(app, db_schema):
    from backend.models import db

    return db.session


@pytest.fixture
def admin_client(client, session):
    from backend.models import AdminUser

    admin = session.query(AdminUser).filter_by(email="relay-admin@test.local").first()
    if not admin:
        admin = AdminUser(
            username="relay_admin",
            email="relay-admin@test.local",
            password_hash="x",
            role="superadmin",
            is_active=True,
        )
        session.add(admin)
        session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin.id)
        sess["user_id"] = admin.id
        sess["admin_id"] = admin.id
        sess["admin_user_id"] = admin.id
        sess["role"] = "superadmin"
        sess["is_authenticated"] = True
        sess["is_admin"] = True
        sess["admin_logged_in"] = True
        sess[client.application.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
        sess["mfa_required"] = True
        sess["mfa_ok_until"] = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()

    return client


def _make_connector(
    session,
    *,
    structure_id: int | None,
    name: str,
    source_slug: str,
    secret: str,
    status: str = "active",
    allowed_fields: list[str] | None = None,
    notes: str | None = None,
):
    from backend.models import IntegrationConnector

    connector = IntegrationConnector(
        structure_id=structure_id,
        name=name,
        source_slug=source_slug,
        api_key_hash=generate_password_hash(secret),
        status=status,
        allowed_fields_json=json.dumps(allowed_fields, ensure_ascii=True) if allowed_fields else None,
        notes=notes,
    )
    session.add(connector)
    session.commit()
    return connector


def test_relay_endpoint_disabled_without_api_key(client):
    os.environ.pop("HC_RELAY_API_KEY", None)

    response = client.post("/api/integrations/relay", json={"external_source": "test"})

    assert response.status_code == 503
    assert response.get_json()["error"] == "Relay integration is not enabled."


def test_relay_endpoint_rejects_invalid_key(client):
    os.environ["HC_RELAY_API_KEY"] = "relay-secret"

    response = client.post(
        "/api/integrations/relay",
        json={"external_source": "test", "external_reference_id": "REQ-1"},
        headers={"X-HC-Relay-Key": "wrong-key"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized relay key."


def test_relay_endpoint_accepts_valid_connector_key(client, session):
    from backend.models import RelayEvent, Structure

    os.environ.pop("HC_RELAY_API_KEY", None)
    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="CCAS Paris",
        source_slug="ccas-paris-relai",
        secret="connector-secret",
        allowed_fields=["status", "priority", "category", "summary_label"],
    )

    response = client.post(
        "/api/integrations/relay",
        json={
            "external_source": "ignored-source",
            "external_reference_id": "REQ-202",
            "status": "A relancer",
            "priority": "Haute",
            "category": "Orientation",
            "summary_label": "Relance coordination",
        },
        headers={
            "X-HC-Connector": connector.source_slug,
            "X-HC-Relay-Key": "connector-secret",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    relay_event = session.get(RelayEvent, body["relay_event_id"])
    connector = session.get(type(connector), connector.id)

    assert relay_event.connector_id == connector.id
    assert relay_event.external_source == connector.source_slug
    assert relay_event.structure_id == structure.id
    assert connector.last_seen_at is not None
    assert connector.last_event_at is not None


def test_relay_endpoint_rejects_invalid_connector_key(client, session):
    from backend.models import Structure

    os.environ.pop("HC_RELAY_API_KEY", None)
    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="CCAS Lyon",
        source_slug="ccas-lyon-relai",
        secret="connector-secret",
    )

    response = client.post(
        "/api/integrations/relay",
        json={
            "external_source": connector.source_slug,
            "external_reference_id": "REQ-401",
        },
        headers={
            "X-HC-Connector": connector.source_slug,
            "X-HC-Relay-Key": "bad-secret",
        },
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized relay key."


def test_relay_endpoint_rejects_paused_connector(client, session):
    from backend.models import Structure

    os.environ.pop("HC_RELAY_API_KEY", None)
    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="CCAS Lille",
        source_slug="ccas-lille-relai",
        secret="connector-secret",
        status="paused",
    )

    response = client.post(
        "/api/integrations/relay",
        json={
            "external_source": connector.source_slug,
            "external_reference_id": "REQ-403",
        },
        headers={
            "X-HC-Connector": connector.source_slug,
            "X-HC-Relay-Key": "connector-secret",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Connector is not active."


def test_relay_endpoint_rejects_non_json_requests(client):
    os.environ["HC_RELAY_API_KEY"] = "relay-secret"

    response = client.post(
        "/api/integrations/relay",
        data="external_source=test",
        content_type="application/x-www-form-urlencoded",
        headers={"X-HC-Relay-Key": "relay-secret"},
    )

    assert response.status_code == 415
    assert response.get_json()["error"] == "JSON body required."


def test_relay_endpoint_rejects_missing_required_fields(client):
    os.environ["HC_RELAY_API_KEY"] = "relay-secret"

    response = client.post(
        "/api/integrations/relay",
        json={"status": "open"},
        headers={"X-HC-Relay-Key": "relay-secret"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "external_source is required"


def test_relay_endpoint_accepts_valid_minimal_payload(client, session):
    from backend.models import RelayEvent, Structure

    os.environ["HC_RELAY_API_KEY"] = "relay-secret"
    structure = session.query(Structure).filter_by(slug="default").first()

    response = client.post(
        "/api/integrations/relay",
        json={
            "external_source": "logiciel-metier",
            "external_reference_id": "DOS-42",
            "status": "A relancer",
            "priority": "Haute",
            "category": "Orientation",
            "structure_slug": "default",
            "summary_label": "Relance dossier logement",
        },
        headers={"X-HC-Relay-Key": "relay-secret"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["ok"] is True
    assert body["sync_status"] == "received"

    relay_event = session.get(RelayEvent, body["relay_event_id"])
    assert relay_event is not None
    assert relay_event.external_source == "logiciel-metier"
    assert relay_event.external_reference_id == "DOS-42"
    assert relay_event.status == "a_relancer"
    assert relay_event.priority == "haute"
    assert relay_event.category == "orientation"
    assert relay_event.structure_id == structure.id
    assert relay_event.summary_label == "Relance dossier logement"


def test_connector_key_is_hashed_not_stored_raw(session):
    from backend.models import Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="CCAS Nantes",
        source_slug="ccas-nantes-relai",
        secret="ultra-secret-key",
    )

    assert connector.api_key_hash != "ultra-secret-key"
    assert check_password_hash(connector.api_key_hash, "ultra-secret-key")


def test_relay_endpoint_persists_only_sanitized_fields(client, session):
    from backend.models import RelayEvent

    os.environ["HC_RELAY_API_KEY"] = "relay-secret"

    response = client.post(
        "/api/integrations/relay",
        json={
            "external_source": "agent-relais",
            "external_reference_id": "SIT-77",
            "status": "en cours",
            "priority": "normale",
            "category": "suivi",
            "diagnosis": "Trouble medical detaille",
            "medical_notes": "Compte rendu clinique",
            "full_name": "Personne Identifiee",
            "upstream_marker": "safe-marker",
        },
        headers={"X-HC-Relay-Key": "relay-secret"},
    )

    assert response.status_code == 201
    body = response.get_json()
    relay_event = session.get(RelayEvent, body["relay_event_id"])

    rejected_fields = json.loads(relay_event.rejected_fields_json)
    assert rejected_fields == ["diagnosis", "full_name", "medical_notes"]

    metadata = json.loads(relay_event.metadata_json)
    assert metadata == {"upstream_marker": "safe-marker"}

    persisted_dump = {
        "external_source": relay_event.external_source,
        "external_reference_id": relay_event.external_reference_id,
        "status": relay_event.status,
        "priority": relay_event.priority,
        "category": relay_event.category,
        "summary_label": relay_event.summary_label,
        "rejected_fields_json": relay_event.rejected_fields_json,
        "metadata_json": relay_event.metadata_json,
    }
    persisted_text = json.dumps(persisted_dump, ensure_ascii=True)
    assert "Trouble medical detaille" not in persisted_text
    assert "Compte rendu clinique" not in persisted_text
    assert "Personne Identifiee" not in persisted_text


def test_admin_integrations_page_loads(admin_client, session):
    from backend.models import RelayEvent, Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="Connecteur Demo",
        source_slug="connecteur-demo",
        secret="connector-secret",
    )
    session.add(
        RelayEvent(
            external_source="connecteur_demo",
            external_reference_id="REL-100",
            status="received",
            priority="haute",
            category="orientation",
            structure_id=structure.id,
            connector_id=connector.id,
            sync_status="received",
            rejected_fields_json='["medical_notes"]',
        )
    )
    session.commit()

    response = admin_client.get("/admin/integrations")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Connecteurs" in html
    assert "Connecteur Demo" in html
    assert "connecteur-demo" in html
    assert "REL-100" in html


def test_admin_connector_detail_page_loads(admin_client, session):
    from backend.models import RelayEvent, Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    connector = _make_connector(
        session,
        structure_id=structure.id,
        name="Connecteur Detail",
        source_slug="connecteur-detail",
        secret="detail-secret",
        allowed_fields=["status", "priority"],
        notes="Usage pilote",
    )
    session.add(
        RelayEvent(
            external_source=connector.source_slug,
            external_reference_id="REL-DETAIL",
            status="received",
            priority="haute",
            category="orientation",
            structure_id=structure.id,
            connector_id=connector.id,
            sync_status="received",
        )
    )
    session.commit()

    response = admin_client.get(f"/admin/integrations/connectors/{connector.id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Connecteur Detail" in html
    assert "connecteur-detail" in html
    assert "REL-DETAIL" in html
    assert "detail-secret" not in html


def test_admin_relay_detail_does_not_expose_sensitive_values(admin_client, session):
    from backend.models import RelayEvent, Structure

    structure = session.query(Structure).filter_by(slug="default").first()
    relay_event = RelayEvent(
        external_source="connecteur_demo",
        external_reference_id="REL-200",
        status="en_cours",
        priority="haute",
        category="orientation",
        structure_id=structure.id,
        sync_status="received",
        rejected_fields_json='["diagnosis","medical_notes","full_name"]',
        metadata_json='{"upstream_marker":"safe-marker"}',
    )
    session.add(relay_event)
    session.commit()

    response = admin_client.get(f"/admin/integrations/relay-events/{relay_event.id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "diagnosis" in html
    assert "medical_notes" in html
    assert "full_name" in html
    assert "safe-marker" in html
    assert "Trouble mÃ©dical dÃ©taillÃ©" not in html
    assert "Compte rendu clinique" not in html
    assert "Personne IdentifiÃ©e" not in html
