from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

from flask import session


CANONICAL_EVENT_TYPES = {
    "page_view",
    "cta_click",
    "form_started",
    "form_submitted",
    "form_abandoned",
}

ANALYTICS_SCOPE_PLATFORM_SALES = "platform_sales"
ANALYTICS_SCOPE_TENANT = "tenant_analytics"

LEGACY_EVENT_COMPATIBILITY = {
    "revenue_cta_click": "cta_click",
    "deployment_pilot_cta_clicked": "cta_click",
    "security_trust_cta_clicked": "cta_click",
    "governance_contact_cta_clicked": "cta_click",
    "structure_deployment_interest": "cta_click",
    "pilot_exchange_requested": "cta_click",
    "professional_access_interest": "cta_click",
    "simulation_pilot_cta_clicked": "cta_click",
    "simulation_deployment_cta_clicked": "cta_click",
    "categories_cta_click": "cta_click",
    "cta_contact_click": "cta_click",
    "cta_access_request_click": "cta_click",
    "demo_form_start": "form_started",
    "form_start": "form_started",
    "sr_form_start": "form_started",
    "form_submit": "form_submitted",
    "demo_form_submit": "form_submitted",
    "contact_form_submit": "form_submitted",
    "access_request_form_submit": "form_submitted",
    "pilot_interest_form_submit": "form_submitted",
}

SESSION_TIMEOUT = timedelta(minutes=30)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def canonical_event_type(event_name: str | None) -> str:
    raw = (event_name or "").strip()
    lowered = raw.lower()
    if lowered in CANONICAL_EVENT_TYPES:
        return lowered
    if lowered in LEGACY_EVENT_COMPATIBILITY:
        return LEGACY_EVENT_COMPATIBILITY[lowered]
    if lowered.startswith("cta_") or lowered.endswith("_cta_clicked"):
        return "cta_click"
    if lowered.endswith("_form_submit"):
        return "form_submitted"
    if lowered.endswith("_form_start"):
        return "form_started"
    return raw[:100] if raw else "unknown"


def validate_analytics_token(value: Any, *, field_name: str) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        from flask import abort

        abort(400, description=f"Invalid {field_name}")
    return value


def analytics_identity(payload: dict[str, Any] | None = None) -> dict[str, str]:
    payload = payload or {}
    props = payload.get("props") or payload.get("properties") or {}

    visitor_id = validate_analytics_token(
        payload.get("visitor_id") or props.get("visitor_id") or session.get("hc_visitor_id"),
        field_name="visitor_id",
    )
    if not visitor_id:
        visitor_id = f"vis_{token_urlsafe(18)}"
        session["hc_visitor_id"] = visitor_id

    now = datetime.now(UTC).replace(tzinfo=None)
    last_seen_raw = session.get("hc_analytics_last_seen")
    expired = False
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(str(last_seen_raw))
            expired = now - last_seen > SESSION_TIMEOUT
        except ValueError:
            expired = True

    incoming_session_id = validate_analytics_token(
        payload.get("session_id") or props.get("session_id"),
        field_name="session_id",
    )
    current_session_id = validate_analytics_token(
        session.get("hc_audience_sid") or session.get("hc_session_id"),
        field_name="session_id",
    )
    session_id = incoming_session_id or ("" if expired else current_session_id)
    if not session_id:
        session_id = f"aud_{token_urlsafe(18)}"

    session["hc_visitor_id"] = visitor_id
    session["hc_session_id"] = session_id
    session["hc_audience_sid"] = session_id
    session["hc_analytics_last_seen"] = now.isoformat()
    return {"visitor_id": visitor_id, "session_id": session_id}


def safe_event_id(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    props = payload.get("props") or payload.get("properties") or {}
    return validate_analytics_token(
        payload.get("event_id") or props.get("event_id"),
        field_name="event_id",
    )


def analytics_properties_json(
    *,
    payload: dict[str, Any] | None,
    original_event_type: str,
    canonical_type: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = payload or {}
    props = payload.get("props") or payload.get("properties") or {}
    metadata = payload.get("metadata") or {}
    safe_props: dict[str, Any] = {}
    for key in (
        "cta",
        "cta_id",
        "cta_name",
        "intent",
        "category",
        "action",
        "label",
        "href",
        "screen",
        "screen_resolution",
        "device",
        "device_type",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    ):
        value = props.get(key) if key in props else payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe_props[key] = value
    data = {
        "schema": "analytics_v2_foundation",
        "original_event_type": original_event_type,
        "canonical_event_type": canonical_type,
        "props": safe_props,
    }
    if isinstance(metadata, dict):
        data["metadata_keys"] = sorted(str(key)[:80] for key in metadata.keys())
    if extra:
        data.update(extra)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
