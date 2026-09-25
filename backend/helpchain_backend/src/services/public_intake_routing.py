from __future__ import annotations

from sqlalchemy import func

from backend.models import (
    Structure,
    StructureCoverageArea,
    StructureService,
)


REQUEST_CATEGORY_TO_SERVICE_CODE = {
    "food": "food",
    "housing": "housing",
    "health": "health",
    "admin_help": "admin",
    "orientation": "orientation",
}


def resolve_public_intake_destination(
    *,
    category: str | None,
    postcode: str | None = None,
    city: str | None = None,
):
    """
    Resolve an anonymous public request to an active structure and service.

    Matching is deliberately conservative:
    - only explicitly supported request categories are routable;
    - the structure must be active;
    - territorial coverage must be active and explicitly match;
    - the service must be active;
    - no Default-tenant fallback is allowed.

    Returns (structure, service) or (None, None).
    """

    category_value = (category or "").strip().lower()
    service_code = REQUEST_CATEGORY_TO_SERVICE_CODE.get(category_value)
    if not service_code:
        return None, None

    postcode_value = (postcode or "").strip()
    city_value = (city or "").strip().lower()

    if not postcode_value and not city_value:
        return None, None

    coverage_query = (
        StructureCoverageArea.query
        .join(
            Structure,
            Structure.id == StructureCoverageArea.structure_id,
        )
        .filter(StructureCoverageArea.is_active.is_(True))
        .filter(func.lower(Structure.status) == "active")
    )

    location_filters = []

    if postcode_value:
        location_filters.append(
            StructureCoverageArea.postal_code == postcode_value
        )

    if city_value:
        location_filters.append(
            func.lower(func.trim(StructureCoverageArea.name)) == city_value
        )

    if not location_filters:
        return None, None

    from sqlalchemy import or_

    coverage = (
        coverage_query
        .filter(or_(*location_filters))
        .order_by(StructureCoverageArea.id.asc())
        .first()
    )

    if coverage is None:
        return None, None

    service = (
        StructureService.query
        .filter(StructureService.structure_id == coverage.structure_id)
        .filter(StructureService.is_active.is_(True))
        .filter(func.lower(StructureService.code) == service_code)
        .order_by(StructureService.id.asc())
        .first()
    )

    if service is None:
        return None, None

    return service.structure, service
