"""Adaptive HelpChain experience.

Maps existing organisation types and capabilities to product modules.

This module controls UI/product exposure only.
It does NOT replace backend authorization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .enterprise_structure_intelligence import ORGANIZATION_TYPES


# Product modules understood by the adaptive UI layer.
MODULE_REGISTRY: dict[str, dict[str, Any]] = {
    "home": {"label": "Accueil"},
    "calendar": {"label": "Calendrier"},
    "workspace": {"label": "Workspace"},
    "requests": {"label": "Demandes"},
    "cases": {"label": "Cas"},
    "referrals": {"label": "Orientations partenaires"},
    "notifications": {"label": "Notifications"},
    "professionals": {"label": "Intervenants"},
    "mobilisation": {"label": "Mobilisation"},
    "risk_triage": {"label": "Risk / Triage"},
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
        "risk_triage",
    ),
    "emergency_assistance": (
        "requests", "cases", "notifications",
        "risk_triage",
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
        "risk_triage",
    ),
    "case_coordination": (
        "requests", "cases", "referrals", "professionals",
    ),
    "medical_assistance": (
        "requests", "cases", "referrals",
    ),
    "emergency_triage": (
        "requests", "cases", "notifications",
        "risk_triage",
    ),
    "security_response": (
        "requests", "cases", "notifications",
    ),
    "risk_escalation": (
        "requests", "cases", "notifications",
        "risk_triage",
    ),
    "emergency_response": (
        "requests", "cases", "notifications",
        "risk_triage",
    ),
    "emergency_medical_response": (
        "requests", "cases", "notifications",
        "risk_triage",
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
        "risk_triage",
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
        "risk_triage",
    ),
    "education_support": (
        "requests", "cases", "referrals",
    ),
    "case_management": (
        "workspace", "requests", "cases",
        "referrals", "professionals",
        "risk_triage",
    ),
}


GLOBAL_ADMIN_MODULES: tuple[str, ...] = tuple(MODULE_REGISTRY)


@dataclass(frozen=True)
class DashboardMetricSlot:
    """Presentation metadata for one existing dashboard metric."""

    key: str
    label: str
    detail_variant: str
    focus: bool = False


@dataclass(frozen=True)
class DashboardProfile:
    """Declarative presentation profile for the shared admin dashboard."""

    key: str
    hero_eyebrow: str
    hero_title: str
    hero_description: str
    hero_metrics: tuple[DashboardMetricSlot, ...]
    show_hero_signal: bool = True
    show_operational_intelligence: bool = True


GENERIC_DASHBOARD_PROFILE = DashboardProfile(
    key="generic",
    hero_eyebrow="Pilotage administratif",
    hero_title="Centre de coordination admin",
    hero_description=(
        "Vue opérationnelle rapide pour prioriser les prochaines actions, "
        "surveiller la pression et garder une lecture territoriale "
        "immédiatement exploitable."
    ),
    hero_metrics=(
        DashboardMetricSlot("priority", "Priorités", "priority_action", True),
        DashboardMetricSlot("follow_up", "Relances", "follow_up_today", True),
        DashboardMetricSlot("territory", "Territoire", "territory"),
        DashboardMetricSlot("flow", "Flux", "flow"),
    ),
)


SCHOOL_DASHBOARD_PROFILE = DashboardProfile(
    key="school",
    hero_eyebrow="Pilotage de l’établissement",
    hero_title="Tableau de bord de l’établissement",
    hero_description=(
        "Suivez les demandes, identifiez les situations à traiter et "
        "organisez les prochaines actions de l’équipe."
    ),
    hero_metrics=(
        DashboardMetricSlot("priority", "Priorités", "situations_to_treat", True),
        DashboardMetricSlot("follow_up", "Relances", "requests_to_follow_up", True),
        DashboardMetricSlot("unassigned", "Sans responsable", "unassigned", True),
        DashboardMetricSlot("stale", "À reprendre", "stale"),
    ),
    show_hero_signal=False,
    show_operational_intelligence=False,
)


CCAS_DASHBOARD_PROFILE = DashboardProfile(
    key="ccas",
    hero_eyebrow="Coordination sociale",
    hero_title="Tableau de bord du CCAS",
    hero_description=(
        "Coordonnez les situations à traiter, planifiez les relances et "
        "assurez le suivi des demandes sans responsable."
    ),
    hero_metrics=(
        DashboardMetricSlot(
            "priority", "Situations à traiter", "situations_to_treat", True
        ),
        DashboardMetricSlot("follow_up", "Relances", "requests_to_follow_up", True),
        DashboardMetricSlot("unassigned", "Sans responsable", "unassigned", True),
        DashboardMetricSlot("stale", "Suivi des situations", "stale"),
    ),
    show_hero_signal=False,
)


DASHBOARD_PROFILES = MappingProxyType(
    {
        "school": SCHOOL_DASHBOARD_PROFILE,
        "ccas": CCAS_DASHBOARD_PROFILE,
    }
)


def resolve_dashboard_profile(structure: Any) -> DashboardProfile:
    """Return presentation metadata without affecting modules or access."""
    organization_type = (
        getattr(structure, "organization_type", None) or ""
    ).strip().lower()
    return DASHBOARD_PROFILES.get(
        organization_type,
        GENERIC_DASHBOARD_PROFILE,
    )


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

    recognized = [
        capability
        for capability in configured
        if capability in CAPABILITY_MODULES
    ]

    if recognized:
        return tuple(dict.fromkeys(recognized))

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
    enabled = {"home", "calendar"}

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
