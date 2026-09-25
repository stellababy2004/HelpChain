from __future__ import annotations

import importlib

import pytest

from backend.models import (
    Structure,
    StructureCoverageArea,
    StructureService,
    db,
)
from backend.helpchain_backend.src.services.public_intake_routing import (
    resolve_public_intake_destination,
)


@pytest.fixture
def routing_app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("HC_DB_PATH", raising=False)
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URI", raising=False)

    import backend.helpchain_backend.src.config as config_module
    import backend.helpchain_backend.src.app as app_module

    importlib.reload(config_module)
    app_module = importlib.reload(app_module)

    app = app_module.create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "PUBLIC_BASE_URL": "https://helpchain.test",
        }
    )

    with app.app_context():
        import backend.models  # noqa: F401
        import backend.models_with_analytics  # noqa: F401

        db.drop_all()
        db.create_all()

        structure = Structure(
            name="CCAS Boulogne-Billancourt",
            slug="ccas-boulogne-billancourt",
            status="active",
        )
        db.session.add(structure)
        db.session.flush()

        db.session.add(
            StructureCoverageArea(
                structure_id=structure.id,
                area_type="city",
                name="Boulogne-Billancourt",
                postal_code="92100",
                is_active=True,
            )
        )

        db.session.add(
            StructureService(
                structure_id=structure.id,
                code="food",
                name="Aide alimentaire",
                is_active=True,
            )
        )

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


def test_public_intake_routes_supported_service(routing_app):
    with routing_app.app_context():
        structure, service = resolve_public_intake_destination(
            category="food",
            postcode="92100",
            city="Boulogne-Billancourt",
        )

        assert structure is not None
        assert structure.slug == "ccas-boulogne-billancourt"
        assert service is not None
        assert service.code == "food"
        assert service.structure_id == structure.id


def test_public_intake_does_not_fallback_for_unsupported_category(routing_app):
    with routing_app.app_context():
        structure, service = resolve_public_intake_destination(
            category="emergency",
            postcode="92100",
            city="Boulogne-Billancourt",
        )

        assert structure is None
        assert service is None


def test_public_intake_does_not_fallback_outside_coverage(routing_app):
    with routing_app.app_context():
        structure, service = resolve_public_intake_destination(
            category="food",
            postcode="75001",
            city="Paris",
        )

        assert structure is None
        assert service is None
