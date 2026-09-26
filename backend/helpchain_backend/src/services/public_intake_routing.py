from __future__ import annotations

from sqlalchemy import func

from backend.models import (
    Structure,
    StructureCoverageArea,
    StructureService,
)
from ..constants.categories import normalize_request_category


# None explicitly marks public categories without an equivalent service capability.
# Do not substitute broad orientation/health services for protection or crisis care.
REQUEST_CATEGORY_TO_SERVICE_CODE: dict[str, str | None] = {
    "food": "food",
    "housing": "housing",
    "health": "health",
    "admin_help": "admin",
    "orientation": "orientation",
    "emergency": None,
    "isolation": None,
    "violence": None,
}

PUBLIC_INTAKE_SERVICE_CODES = frozenset(
    code for code in REQUEST_CATEGORY_TO_SERVICE_CODE.values() if code is not None
)


def _eligible_public_intake_services():
    return (
        StructureService.query
        .join(Structure, Structure.id == StructureService.structure_id)
        .join(StructureCoverageArea, Structure.id == StructureCoverageArea.structure_id)
        .filter(func.lower(Structure.status) == "active")
        .filter(StructureCoverageArea.is_active.is_(True))
        .filter(StructureService.is_active.is_(True))
        .filter(func.lower(StructureService.code).in_(PUBLIC_INTAKE_SERVICE_CODES))
    )


def is_public_intake_routing_ready(structure_id: int) -> bool:
    """Check configured routing eligibility, not coverage for a specific location."""
    return (
        _eligible_public_intake_services()
        .filter(StructureService.structure_id == structure_id)
        .first()
        is not None
    )


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

    category_value = normalize_request_category(category)
    service_code = REQUEST_CATEGORY_TO_SERVICE_CODE.get(category_value)
    if not service_code:
        return None, None

    postcode_value = (postcode or "").strip()
    city_value = (city or "").strip().lower()

    if not postcode_value and not city_value:
        return None, None

    service_query = (
        _eligible_public_intake_services()
        .filter(func.lower(StructureService.code) == service_code)
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

    # Preserve stable coverage/service ID ordering among eligible destinations.
    # More advanced capacity/SLA routing may be added later.
    service = (
        service_query
        .filter(or_(*location_filters))
        .order_by(StructureCoverageArea.id.asc(), StructureService.id.asc())
        .first()
    )

    if service is None:
        return None, None

    return service.structure, service
