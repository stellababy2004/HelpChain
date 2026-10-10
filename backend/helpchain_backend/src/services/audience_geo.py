"""Optional, local-only approximate GeoIP lookup.

Disabled unless AUDIENCE_GEOIP_ENABLED is explicitly true and a licensed,
up-to-date GeoLite2-City MMDB file is configured. Never sends visitor IPs
to an external API. This helper must only be called after the applicable
audience-consent/privacy policy has been enforced by its caller.
"""
from __future__ import annotations

import ipaddress
from pathlib import Path

from flask import current_app


def approximate_audience_location(ip_address: str | None) -> str | None:
    if not current_app.config.get("AUDIENCE_GEOIP_ENABLED", False):
        return None
    database_path = current_app.config.get("AUDIENCE_GEOIP_DATABASE_PATH")
    if not database_path or not Path(database_path).is_file():
        return None
    try:
        ip = ipaddress.ip_address(ip_address or "")
        if not ip.is_global:
            return None
        import geoip2.database

        with geoip2.database.Reader(str(database_path)) as reader:
            result = reader.city(str(ip))
        country = result.country.iso_code
        city = result.city.name
        if not country or not city:
            return None
        # City and country only: no coordinates, postal code or IP persisted.
        if len(city) > 70 or len(country) != 2:
            return None
        return f"{city}, {country}"
    except (ValueError, ImportError, OSError):
        return None
    except Exception:
        current_app.logger.warning("Audience city lookup unavailable")
        return None
