from __future__ import annotations

import importlib
import re

import pytest

from backend.models import (
    Structure,
    StructureCoverageArea,
    StructureService,
    db,
)
from backend.helpchain_backend.src.services.public_intake_routing import (
    PUBLIC_INTAKE_SERVICE_CODES,
    REQUEST_CATEGORY_TO_SERVICE_CODE,
    is_public_intake_routing_ready,
    resolve_public_intake_destination,
)
from backend.helpchain_backend.src.constants.categories import REQUEST_CATEGORY_CODES


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


def test_public_intake_category_contract_is_complete(routing_app):
    assert REQUEST_CATEGORY_TO_SERVICE_CODE == {
        "food": "food",
        "housing": "housing",
        "health": "health",
        "admin_help": "admin",
        "orientation": "orientation",
        "emergency": None,
        "isolation": None,
        "violence": None,
    }
    assert set(REQUEST_CATEGORY_CODES) == set(REQUEST_CATEGORY_TO_SERVICE_CODE)
    assert PUBLIC_INTAKE_SERVICE_CODES == {
        "food", "housing", "health", "admin", "orientation"
    }

    client = routing_app.test_client()
    response = client.get("/submit_request")
    assert response.status_code == 200
    category_select = re.search(
        r'<select[^>]*id="srCategory"[^>]*>(.*?)</select>',
        response.get_data(as_text=True),
        re.DOTALL,
    )
    assert category_select is not None
    rendered_categories = set(re.findall(r'<option value="([^"]+)"', category_select[1]))
    assert rendered_categories == set(REQUEST_CATEGORY_TO_SERVICE_CODE)

    response = client.get("/orienter")
    assert response.status_code == 200
    orienter_categories = set(re.findall(
        r'/submit_request\?category=([a-z_]+)', response.get_data(as_text=True)
    ))
    assert orienter_categories == {"food", "admin_help", "isolation", "health", "emergency"}
    assert orienter_categories <= set(REQUEST_CATEGORY_TO_SERVICE_CODE)


@pytest.mark.parametrize("category, code", [
    ("food", "food"),
    ("housing", "housing"),
    ("health", "health"),
    ("admin_help", "admin"),
    ("orientation", "orientation"),
    (" social ", "orientation"),
    ("MEDICAL", "health"),
    ("admin", "admin"),
    ("hebergement", "housing"),
])
def test_public_intake_contract_routes_canonical_categories_and_aliases(
    routing_app, category, code
):
    with routing_app.app_context():
        expected_service = StructureService.query.one()
        expected_service.code = code
        db.session.commit()

        structure, service = resolve_public_intake_destination(
            category=category, postcode="92100"
        )
        assert service.id == expected_service.id
        assert structure.id == expected_service.structure_id


@pytest.mark.parametrize("category", ["emergency", "isolation", "violence", "unknown"])
def test_public_intake_unsupported_category_cannot_route_to_same_named_service(
    routing_app, category
):
    with routing_app.app_context():
        StructureService.query.one().code = category
        db.session.commit()

        assert resolve_public_intake_destination(
            category=category, postcode="92100"
        ) == (None, None)
        assert not is_public_intake_routing_ready(Structure.query.one().id)


@pytest.mark.parametrize("missing_requirement", [
    "inactive_structure", "missing_coverage", "inactive_coverage",
    "missing_service", "inactive_service", "internal_service",
])
def test_public_intake_readiness_requires_all_routing_requirements(
    routing_app, missing_requirement
):
    with routing_app.app_context():
        structure = Structure.query.one()
        coverage = StructureCoverageArea.query.one()
        service = StructureService.query.one()
        if missing_requirement == "inactive_structure":
            structure.status = "inactive"
        elif missing_requirement == "missing_coverage":
            db.session.delete(coverage)
        elif missing_requirement == "inactive_coverage":
            coverage.is_active = False
        elif missing_requirement == "missing_service":
            db.session.delete(service)
        elif missing_requirement == "inactive_service":
            service.is_active = False
        else:
            service.code = "internal-coordination"
        db.session.commit()

        assert not is_public_intake_routing_ready(structure.id)


@pytest.mark.parametrize("code", ["food", "housing", "health", "admin", "orientation", "FOOD"])
def test_public_intake_readiness_with_active_routable_service(routing_app, code):
    with routing_app.app_context():
        structure = Structure.query.one()
        StructureService.query.one().code = code
        db.session.commit()

        assert is_public_intake_routing_ready(structure.id)


def test_public_intake_readiness_does_not_borrow_another_structures_coverage(routing_app):
    with routing_app.app_context():
        structure = Structure(name="No coverage", slug="no-coverage", status="active")
        db.session.add(structure)
        db.session.flush()
        db.session.add(StructureService(
            structure_id=structure.id, name="Food", code="food", is_active=True
        ))
        db.session.commit()

        assert not is_public_intake_routing_ready(structure.id)


@pytest.mark.parametrize("postcode, city", [(None, None), ("", ""), ("  ", "  ")])
def test_public_intake_requires_location(routing_app, postcode, city):
    with routing_app.app_context():
        assert resolve_public_intake_destination(
            category="food", postcode=postcode, city=city
        ) == (None, None)


@pytest.mark.parametrize("inactive_part", ["structure", "coverage", "service"])
def test_public_intake_ignores_inactive_destination(routing_app, inactive_part):
    with routing_app.app_context():
        if inactive_part == "structure":
            Structure.query.one().status = "inactive"
        elif inactive_part == "coverage":
            StructureCoverageArea.query.one().is_active = False
        else:
            StructureService.query.one().is_active = False
        db.session.commit()

        assert resolve_public_intake_destination(
            category="food", postcode="92100"
        ) == (None, None)


def test_public_intake_ignores_missing_required_service(routing_app):
    with routing_app.app_context():
        assert resolve_public_intake_destination(
            category="health", postcode="92100"
        ) == (None, None)


@pytest.mark.parametrize("city", [None, "Different city"])
def test_public_intake_matches_postcode_independently(routing_app, city):
    with routing_app.app_context():
        structure, service = resolve_public_intake_destination(
            category="food", postcode=" 92100 ", city=city
        )

        assert structure.slug == "ccas-boulogne-billancourt"
        assert service.code == "food"
        assert service.structure_id == structure.id


@pytest.mark.parametrize("postcode", [None, "75001"])
def test_public_intake_matches_normalized_city_independently(routing_app, postcode):
    with routing_app.app_context():
        StructureCoverageArea.query.one().name = "  BOULOGNE-billancourt  "
        db.session.commit()

        structure, service = resolve_public_intake_destination(
            category="food", postcode=postcode, city="  boulogne-BILLANCOURT  "
        )

        assert structure.slug == "ccas-boulogne-billancourt"
        assert service.code == "food"
        assert service.structure_id == structure.id


def _add_overlapping_destination(*, slug, service_code):
    structure = Structure(name=slug, slug=slug, status="active")
    db.session.add(structure)
    db.session.flush()
    coverage = StructureCoverageArea(
        structure_id=structure.id,
        area_type="city",
        name="Boulogne-Billancourt",
        postal_code="92100",
        is_active=True,
    )
    service = StructureService(
        structure_id=structure.id,
        code=service_code,
        name=service_code,
        is_active=True,
    )
    db.session.add_all([coverage, service])
    db.session.commit()
    return structure, coverage, service


@pytest.mark.parametrize(
    "location",
    [{"postcode": "92100"}, {"city": "Boulogne-Billancourt"}],
    ids=["postcode", "city"],
)
def test_public_intake_skips_first_structure_without_required_service(
    routing_app, location
):
    with routing_app.app_context():
        first_structure = Structure.query.one()
        first_coverage = StructureCoverageArea.query.one()
        expected_structure, second_coverage, expected_service = (
            _add_overlapping_destination(
                slug="second-health-provider", service_code="health"
            )
        )
        assert first_structure.id < expected_structure.id
        assert first_coverage.id < second_coverage.id

        structure, service = resolve_public_intake_destination(
            category="health", **location
        )

        assert structure.id == expected_structure.id
        assert service.id == expected_service.id
        assert service.structure_id == structure.id


@pytest.mark.parametrize("earliest_coverage", ["first", "second"])
def test_public_intake_overlap_uses_stable_coverage_order(routing_app, earliest_coverage):
    with routing_app.app_context():
        destinations = []
        for label in ("first", "second"):
            structure = Structure(
                name=f"{label} Paris provider",
                slug=f"{label}-paris-provider",
                status="active",
            )
            db.session.add(structure)
            db.session.flush()
            service = StructureService(
                structure_id=structure.id,
                code="food",
                name="Food",
                is_active=True,
            )
            db.session.add(service)
            db.session.flush()
            destinations.append((structure, service))

        # Insert coverage independently of structure/service creation order.
        coverage_order = (
            destinations if earliest_coverage == "first" else destinations[::-1]
        )
        coverages = []
        for structure, _ in coverage_order:
            coverage = StructureCoverageArea(
                structure_id=structure.id,
                area_type="city",
                name="Paris",
                postal_code="75001",
                is_active=True,
            )
            db.session.add(coverage)
            db.session.flush()
            coverages.append(coverage)
        db.session.commit()

        assert coverages[0].id < coverages[1].id
        expected_structure, expected_service = coverage_order[0]

        for _ in range(3):
            structure, service = resolve_public_intake_destination(
                category="food", postcode="75001", city="Paris"
            )
            assert structure.id == expected_structure.id
            assert service.id == expected_service.id
            assert service.structure_id == structure.id
