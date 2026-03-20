from __future__ import annotations

import re
from typing import Optional


DEFAULT_REQUEST_COUNTRY = "France"
GEOCODING_STATUS_GEOCODED = "geocoded"
GEOCODING_STATUS_INCOMPLETE = "incomplete"
GEOCODING_STATUS_NEEDS_REVIEW = "needs_review"

_WHITESPACE_RE = re.compile(r"\s+")
_POSTCODE_CITY_RE = re.compile(
    r"(?P<postcode>\d{4,10})[\s,;-]+(?P<city>[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,})$"
)


def _clean_text(value, *, max_length: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = _WHITESPACE_RE.sub(" ", text)
    if max_length is not None:
        text = text[:max_length]
    return text or None


def normalize_request_country(country: str | None) -> str | None:
    text = _clean_text(country, max_length=120)
    if not text:
        return DEFAULT_REQUEST_COUNTRY
    lowered = text.casefold()
    if lowered in {"fr", "france"}:
        return DEFAULT_REQUEST_COUNTRY
    return text


def request_address_display_text(
    *,
    address_line: str | None = None,
    postcode: str | None = None,
    city: str | None = None,
    country: str | None = None,
    fallback_text: str | None = None,
) -> str | None:
    address_line = _clean_text(address_line, max_length=255)
    postcode = _clean_text(postcode, max_length=32)
    city = _clean_text(city, max_length=200)
    fallback_text = _clean_text(fallback_text, max_length=500)

    has_structured_parts = any((address_line, postcode, city, country))
    country_value = normalize_request_country(country) if has_structured_parts else None
    locality = " ".join(part for part in (postcode, city) if part)

    parts = []
    if address_line:
        parts.append(address_line)
    if locality:
        parts.append(locality)
    if country_value:
        parts.append(country_value)

    if parts:
        return _clean_text(", ".join(parts), max_length=500)
    return fallback_text


def _parse_location_text(location_text: str | None) -> dict[str, str | None]:
    text = _clean_text(location_text, max_length=500)
    if not text:
        return {
            "address_line": None,
            "postcode": None,
            "city": None,
            "country": None,
        }

    parts = [part.strip() for part in text.split(",") if part and part.strip()]
    search_target = parts[-1] if parts else text
    match = _POSTCODE_CITY_RE.search(search_target)
    if not match:
        return {
            "address_line": None,
            "postcode": None,
            "city": None,
            "country": None,
        }

    postcode = _clean_text(match.group("postcode"), max_length=32)
    city = _clean_text(match.group("city"), max_length=200)

    address_line = None
    if parts:
        if len(parts) >= 2:
            address_line = _clean_text(", ".join(parts[:-1]), max_length=255)
        else:
            prefix = search_target[: match.start()].strip(" ,;-")
            address_line = _clean_text(prefix, max_length=255)

    return {
        "address_line": address_line,
        "postcode": postcode,
        "city": city,
        "country": DEFAULT_REQUEST_COUNTRY,
    }


def resolve_request_geolocation(
    *,
    address_line: str | None = None,
    postcode: str | None = None,
    city: str | None = None,
    country: str | None = None,
    location_text: str | None = None,
    timeout_seconds: float = 2.5,
) -> dict[str, object]:
    address_line = _clean_text(address_line, max_length=255)
    postcode = _clean_text(postcode, max_length=32)
    city = _clean_text(city, max_length=200)
    location_text = _clean_text(location_text, max_length=500)
    country = _clean_text(country, max_length=120)

    parsed = _parse_location_text(location_text)
    if address_line is None:
        address_line = parsed["address_line"]
    if postcode is None:
        postcode = parsed["postcode"]
    if city is None:
        city = parsed["city"]

    has_any_address = any((address_line, postcode, city, location_text))
    if country and country.casefold() not in {"fr", "france"}:
        has_any_address = True
    country_value = normalize_request_country(country) if has_any_address else None
    normalized_address = request_address_display_text(
        address_line=address_line,
        postcode=postcode,
        city=city,
        country=country_value,
        fallback_text=location_text,
    )

    geocode_query = None
    if address_line and postcode and city:
        geocode_query = request_address_display_text(
            address_line=address_line,
            postcode=postcode,
            city=city,
            country=country_value,
        )
    elif postcode and city:
        geocode_query = request_address_display_text(
            postcode=postcode,
            city=city,
            country=country_value,
        )

    result: dict[str, object] = {
        "address_line": address_line,
        "postcode": postcode,
        "city": city,
        "country": country_value,
        "normalized_address": normalized_address,
        "location_text": normalized_address or location_text,
        "latitude": None,
        "longitude": None,
        "geocoding_status": GEOCODING_STATUS_INCOMPLETE,
    }

    if not geocode_query:
        return result

    lat, lng = geocode_location_best_effort(
        location_text=geocode_query,
        city=city,
        timeout_seconds=timeout_seconds,
    )
    if lat is None or lng is None:
        result["geocoding_status"] = GEOCODING_STATUS_NEEDS_REVIEW
        return result

    result["latitude"] = lat
    result["longitude"] = lng
    result["geocoding_status"] = GEOCODING_STATUS_GEOCODED
    return result


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def geocode_location_best_effort(
    *,
    location_text: str | None = None,
    city: str | None = None,
    timeout_seconds: float = 2.5,
) -> tuple[Optional[float], Optional[float]]:
    """
    Best-effort geocoding via Nominatim (OpenStreetMap).
    Never raises: returns (None, None) on any failure.
    """
    try:
        import requests  # existing dependency in this project
    except Exception:
        return None, None

    candidates = []
    if location_text and str(location_text).strip():
        candidates.append(str(location_text).strip())
    if city and str(city).strip():
        c = str(city).strip()
        if c not in candidates:
            candidates.append(c)

    if not candidates:
        return None, None

    headers = {
        "User-Agent": "HelpChain/1.0 (contact@helpchain.live)",
        "Accept": "application/json",
    }
    endpoint = "https://nominatim.openstreetmap.org/search"

    for query in candidates:
        try:
            resp = requests.get(
                endpoint,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 0,
                },
                headers=headers,
                timeout=timeout_seconds,
            )
            if not resp.ok:
                continue
            data = resp.json() or []
            if not data:
                continue
            first = data[0] or {}
            lat = _to_float(first.get("lat"))
            lng = _to_float(first.get("lon"))
            if lat is None or lng is None:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                continue
            return lat, lng
        except Exception:
            continue

    return None, None
