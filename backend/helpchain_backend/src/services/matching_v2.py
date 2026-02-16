import math
from datetime import UTC, datetime, timezone

from backend.helpchain_backend.src.models import Request


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def normalize_text(s: str) -> str:
    return (s or "").strip().lower()


def tokens_from_skills(skills_text: str):
    if not skills_text:
        return []
    return [t.strip().lower() for t in skills_text.split(",") if t.strip()]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        dlambda / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def age_hours(dt):
    if not dt:
        return 9999
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def score_text_skills(volunteer, req) -> float:
    # 0..40
    skills = tokens_from_skills(getattr(volunteer, "skills", ""))
    if not skills:
        return 0.0

    title = normalize_text(getattr(req, "title", ""))
    desc = normalize_text(getattr(req, "description", "")) or normalize_text(
        getattr(req, "message", "")
    )
    cat = normalize_text(getattr(req, "category", ""))

    hits = 0
    for sk in skills:
        if sk and sk in title:
            hits += 2
        if sk and sk in desc:
            hits += 1
        if sk and sk in cat:
            hits += 1

    return clamp(hits * 4, 0, 40)


def score_city(volunteer, req) -> float:
    # 0..15
    vloc = normalize_text(getattr(volunteer, "location", ""))
    rcity = normalize_text(getattr(req, "city", ""))
    rregion = normalize_text(getattr(req, "region", ""))

    if not vloc or (not rcity and not rregion):
        return 0.0

    if vloc and rcity and (vloc in rcity or rcity in vloc):
        return 15.0
    if vloc and rregion and (vloc in rregion or rregion in vloc):
        return 10.0
    return 0.0


def score_distance(volunteer, req) -> float:
    # 0..20
    vlat = getattr(volunteer, "latitude", None)
    vlon = getattr(volunteer, "longitude", None)
    rlat = getattr(req, "latitude", None)
    rlon = getattr(req, "longitude", None)

    if vlat is None or vlon is None or rlat is None or rlon is None:
        return 0.0

    km = haversine_km(vlat, vlon, rlat, rlon)

    if km <= 5:
        return 20.0
    if km <= 20:
        return 20.0 - (km - 5) * (8.0 / 15.0)
    if km <= 50:
        return 12.0 - (km - 20) * (8.0 / 30.0)
    return 0.0


def distance_km_or_none(volunteer, req):
    vlat = getattr(volunteer, "latitude", None)
    vlon = getattr(volunteer, "longitude", None)
    rlat = getattr(req, "latitude", None)
    rlon = getattr(req, "longitude", None)
    if vlat is None or vlon is None or rlat is None or rlon is None:
        return None
    try:
        return round(haversine_km(vlat, vlon, rlat, rlon), 1)
    except Exception:
        return None


def score_priority(req) -> float:
    # 0..15
    p = getattr(req, "priority", None)
    if p is None:
        return 0.0

    if isinstance(p, int):
        return clamp((p - 1) * 3.75, 0, 15)

    ptxt = normalize_text(str(p))
    if ptxt in ("high", "urgent", "critical"):
        return 15.0
    if ptxt in ("medium", "normal"):
        return 8.0
    return 2.0


def score_activity(volunteer) -> float:
    # 0..10
    last = getattr(volunteer, "last_active_at", None) or getattr(
        volunteer, "last_activity", None
    )
    if not last:
        return 4.0
    h = age_hours(last)
    if h <= 24:
        return 10.0
    if h <= 24 * 7:
        return 6.0
    return 4.0


def urgency_multiplier(req) -> float:
    # 0.8..1.2
    created = getattr(req, "created_at", None)
    h = age_hours(created)

    if h <= 6:
        base = 1.2
    elif h <= 24:
        base = 1.1
    elif h <= 72:
        base = 1.0
    else:
        base = 0.9

    status = normalize_text(getattr(req, "status", ""))
    if status in ("done", "completed", "resolved", "closed"):
        base *= 0.8
    return clamp(base, 0.8, 1.2)


def match_score(volunteer, req):
    parts = {
        "text": score_text_skills(volunteer, req),
        "city": score_city(volunteer, req),
        "distance": score_distance(volunteer, req),
        "priority": score_priority(req),
        "activity": score_activity(volunteer),
    }
    raw = sum(parts.values())
    parts["distance_km"] = distance_km_or_none(volunteer, req)
    mult = urgency_multiplier(req)
    final = clamp(raw * mult, 0, 100)
    return final, parts, mult


def _created_sort_key(req):
    dt = getattr(req, "created_at", None)
    if not dt:
        return datetime.min
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def get_matched_requests_v2(volunteer, limit=12, min_percent=55):
    reqs = (
        Request.query.filter(Request.deleted_at.is_(None))
        .filter(Request.is_archived.is_(False))
        .filter(Request.assigned_volunteer_id.is_(None))
        .all()
    )

    scored = []
    for r in reqs:
        score, parts, mult = match_score(volunteer, r)
        percent = int(round(score))
        if percent >= int(min_percent):
            scored.append((r, percent, parts, mult))

    scored.sort(key=lambda x: (x[1], _created_sort_key(x[0])), reverse=True)
    return scored[: int(limit)]
