"""Adaptive HelpChain experience.

Maps existing organisation types and capabilities to product modules.

This module controls UI/product exposure only.
It does NOT replace backend authorization.
"""

from __future__ import annotations

import json
from typing import Any

from .enterprise_structure_intelligence import ORGANIZATION_TYPES


# Product modules understood by the adaptive UI layer.
MODULE_REGISTRY: dict[str, dict[str, Any]] = {
    "home": {"label": "Accueil"},
    "workspace": {"label": "Workspace"},
    "requests": {"label": "Demandes"},
    "cases": {"label": "Cas"},
    "referrals": {"label": "Orientations partenaires"},
    "notifications": {"label": "Notifications"},
    "professionals": {"label": "Intervenants"},
    "mobilisation": {"label": "Mobilisation"},
    "pilotage": {"label": "Pilotage op?rationnel"},
    "maps": {"label": "Cartes"},
    "reports": {"label": "Rapports"},
    "connectors": {"label": "Connecteurs"},
    "security": {"label": "S?curit?"},
    "platform": {"label": "Plateforme"},
}


# Capabilities already present in HelpChain are translated into UI modules.
CAPABILITY_MODULES: dict[str, tuple[str, ...]] = {
    "territorial_coordination": (
        "workspace", "requests", "cases", "referrals",
        "professionals", "pilotage", "maps", "reports",
    ),
    "public_case_intake": (
        "requests", "cases",
    ),
    "social_support": (
        "workspace", "requests", "cases", "referrals",
    ),
    "emergency_assistance": (
        "requests", "cases", "notifications",
    ),
    "volunteer_coordination": (
        "workspace", "requests", "mobilisation", "notifications",
    ),
    "field_support": (
        "requests", "cases", "mobilisation",
    ),
    "humanitarian_response": (
        "workspace", "requests", "cases",
        "mobilisation", "notifications", "reports",
    ),
    "case_coordination": (
        "requests", "cases", "referrals", "professionals",
    ),
    "medical_assistance": (
        "requests", "cases", "referrals",
    ),
    "emergency_triage": (
        "requests", "cases", "notifications",
    ),
    "security_response": (
        "requests", "cases", "notifications",
    ),
    "risk_escalation": (
        "requests", "cases", "notifications",
    ),
    "emergency_response": (
        "requests", "cases", "notifications",
    ),
    "emergency_medical_response": (
        "requests", "cases", "notifications",
    ),
    "financial_assistance": (
        "requests", "cases", "referrals",
    ),
    "benefits_guidance": (
        "requests", "cases", "referrals",
    ),
    "territorial_governance": (
        "workspace", "requests", "cases",
        "pilotage", "maps", "reports",
    ),
    "crisis_coordination": (
        "requests", "cases", "referrals",
        "notifications", "pilotage", "maps",
    ),
    "legal_assistance": (
        "requests", "cases", "referrals",
    ),
    "protection_orders": (
        "requests", "cases", "notifications",
    ),
    "volunteer_dispatch": (
        "requests", "mobilisation", "notifications",
    ),
    "food_assistance": (
        "requests", "cases",
    ),
    "emergency_housing": (
        "requests", "cases", "referrals",
    ),
    "child_support": (
        "requests", "cases", "referrals",
    ),
    "education_support": (
        "requests", "cases", "referrals",
    ),
    "case_management": (
        "workspace", "requests", "cases",
        "referrals", "professionals",
    ),
}


GLOBAL_ADMIN_MODULES: tuple[str, ...] = tuple(MODULE_REGISTRY)


def _json_list(value: Any) -> list[str]:
    """Normalize a JSON/list capability value."""
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

        if isinstance(decoded, list):
            return [
                str(item).strip()
                for item in decoded
                if str(item).strip()
            ]

    return []


def organization_capabilities(structure: Any) -> tuple[str, ...]:
    """Return configured capabilities or defaults for the organisation type."""
    configured = _json_list(
        getattr(structure, "capabilities_json", None)
    )

    if configured:
        return tuple(dict.fromkeys(configured))

    organization_type = (
        getattr(structure, "organization_type", None) or ""
    ).strip().lower()

    definition = ORGANIZATION_TYPES.get(organization_type, {})

    return tuple(
        dict.fromkeys(definition.get("default_capabilities", ()))
    )


def modules_for_capabilities(
    capabilities: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Translate operational capabilities into visible product modules."""
    enabled = {"home"}

    for capability in capabilities:
        enabled.update(CAPABILITY_MODULES.get(capability, ()))

    # Preserve product navigation order.
    return tuple(
        module
        for module in MODULE_REGISTRY
        if module in enabled
    )


def adaptive_modules(
    structure: Any,
    *,
    global_admin: bool = False,
) -> tuple[str, ...]:
    """Return modules appropriate for the current organisation experience."""
    if global_admin:
        return GLOBAL_ADMIN_MODULES

    return modules_for_capabilities(
        organization_capabilities(structure)
    )


def module_enabled(
    structure: Any,
    module: str,
    *,
    global_admin: bool = False,
) -> bool:
    """Convenience check for templates/navigation."""
    return module in adaptive_modules(
        structure,
        global_admin=global_admin,
    )
