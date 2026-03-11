from __future__ import annotations

from typing import Optional


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

