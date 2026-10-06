"""Tenant boundaries for website telemetry; never resolve tenants from ambient g."""

from flask import abort, current_app, request, session
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import or_

from backend.extensions import db
from backend.models import Structure
from backend.models_with_analytics import AnalyticsEvent
from .analytics_v2 import ANALYTICS_SCOPE_TENANT
from ..admin_actor import BearerActorResolutionError, resolve_current_admin_actor
from ..admin_policies import can_view_global_analytics


def analytics_actor():
    try:
        return resolve_current_admin_actor()
    except BearerActorResolutionError:
        abort(403)


def _selectors(payload=None):
    """Inspect all supplied values, including duplicate query parameters."""
    sources = [request.args]
    if isinstance(payload, dict):
        sources.append(payload)
        for key in ("props", "properties", "metadata"):
            if isinstance(payload.get(key), dict):
                sources.append(payload[key])
    for source in sources:
        for key in ("structure_id", "organization_id", "site_id", "tracking_id"):
            if key in source:
                values = source.getlist(key) if hasattr(source, "getlist") else [source[key]]
                for value in values:
                    yield key, value
    for header in ("X-Structure-ID", "X-Organization-ID", "X-Site-ID"):
        if header in request.headers:
            yield "site_id" if header == "X-Site-ID" else "structure_id", request.headers[header]


def validate_selectors(structure, payload=None):
    for key, value in _selectors(payload):
        expected = structure.slug if key in {"site_id", "tracking_id"} else structure.id
        if str(value) != str(expected):
            abort(403)


def has_tenant_selectors(payload=None):
    return next(_selectors(payload), None) is not None


def read_scope():
    actor = analytics_actor()
    if not actor.is_admin:
        abort(403)
    payload = request.get_json(silent=True)
    selectors = list(_selectors(payload))
    if can_view_global_analytics(actor):
        if not selectors:
            return None
        key, value = selectors[0]
        if key in {"site_id", "tracking_id"}:
            structure = Structure.query.filter_by(slug=str(value)).first()
        else:
            try:
                structure = db.session.get(Structure, int(value))
            except (ValueError, TypeError):
                abort(403)
    else:
        structure = db.session.get(Structure, actor.structure_id) if actor.structure_id else None
    if structure is None:
        abort(403)
    validate_selectors(structure, payload)
    return structure


def scoped_events(structure):
    query = AnalyticsEvent.query.filter(
        or_(
            AnalyticsEvent.analytics_scope == ANALYTICS_SCOPE_TENANT,
            AnalyticsEvent.analytics_scope.is_(None),
        )
    )
    return query.filter_by(structure_id=structure.id) if structure is not None else query


def scope_description(structure):
    if structure is None:
        return {"structure_id": None, "site_id": None, "name": "All organizations / sites", "website": None}
    return {"structure_id": structure.id, "site_id": structure.slug,
            "name": structure.name, "website": structure.website}


def first_party_structure():
    # Existing deployment-owned slug, not a client header, URL, or logged-in tenant.
    from backend.core.tenant import TENANT_DEFAULT_SLUG

    structure = Structure.query.filter_by(slug=TENANT_DEFAULT_SLUG).first()
    if structure is None:
        abort(503, description="First-party analytics site is not configured")
    return structure


def _signer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="website-analytics-ingestion-v1")


def ingestion_token(structure):
    """Backend-only credential, bound to the immutable tenant ID and current slug."""
    return _signer().dumps({"structure_id": structure.id, "site_id": structure.slug})


def ingestion_structure(payload):
    site_id = payload.get("site_id")
    token = request.headers.get("X-Analytics-Key", "")
    if not isinstance(site_id, str) or not site_id or not token:
        abort(403)
    try:
        claims = _signer().loads(token)
    except BadSignature:
        abort(403)
    if not isinstance(claims, dict) or claims.get("site_id") != site_id:
        abort(403)
    structure_id = claims.get("structure_id")
    if type(structure_id) is not int:
        abort(403)
    structure = db.session.get(Structure, structure_id)
    if structure is None or structure.slug != site_id:
        abort(403)
    # Credentials do not override an authenticated organization user's tenant.
    actor = analytics_actor()
    if actor.is_authenticated:
        if not actor.is_admin or (not can_view_global_analytics(actor) and actor.structure_id != structure.id):
            abort(403)
    elif session.get("admin_logged_in"):
        abort(403)
    validate_selectors(structure, payload)
    return structure
