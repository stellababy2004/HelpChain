from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

from backend.helpchain_backend.src.models import (
    Request,
    Volunteer,
    VolunteerMatchFeedback,
    db,
)
from flask import current_app
from sqlalchemy import or_
from sqlalchemy.exc import DatabaseError, OperationalError

_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]+", re.UNICODE)
_MATCH_CACHE: dict[str, tuple[float, list[tuple[int, int, dict]]]] = {}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _tokens(s: str | None) -> list[str]:
    return _WORD_RE.findall(_norm(s))


def _volunteer_skill_tokens(volunteer: Volunteer) -> list[str]:
    return _tokens(getattr(volunteer, "skills", "") or "")


def _request_text(req: Request, max_chars: int = 800) -> str:
    parts = [
        (getattr(req, "title", "") or "")[:200],
        (getattr(req, "description", "") or "")[:max_chars],
        (getattr(req, "message", "") or "")[:max_chars],
        (getattr(req, "category", "") or "")[:100],
        (getattr(req, "city", "") or "")[:100],
        (getattr(req, "region", "") or "")[:100],
        (getattr(req, "location_text", "") or "")[:200],
    ]
    return " ".join([p for p in parts if p])


def _score_location(vol_location: str, req: Request) -> int:
    # 0..25
    v = _norm(vol_location)
    if not v:
        return 0

    candidates = " ".join(
        [
            _norm(getattr(req, "city", "")),
            _norm(getattr(req, "region", "")),
            _norm(getattr(req, "location_text", "")),
        ]
    ).strip()
    if not candidates:
        return 0

    if v in candidates:
        return 25

    vt = set(_tokens(v))
    ct = set(_tokens(candidates))
    if not vt or not ct:
        return 0

    overlap = len(vt & ct) / max(1, len(vt))
    if overlap >= 0.6:
        return 18
    if overlap >= 0.3:
        return 10
    return 0


def _score_skills(volunteer: Volunteer, req: Request, max_text_chars: int = 800) -> int:
    # 0..45
    skills = _volunteer_skill_tokens(volunteer)
    if not skills:
        return 0

    req_tokens = set(_tokens(_request_text(req, max_chars=max_text_chars)))
    if not req_tokens:
        return 0

    hits = sum(1 for s in set(skills) if s in req_tokens)
    if hits >= 6:
        return 45
    if hits == 5:
        return 40
    if hits == 4:
        return 34
    if hits == 3:
        return 28
    if hits == 2:
        return 20
    if hits == 1:
        return 12
    return 0


def _score_priority(req: Request) -> int:
    # 0..20
    p = getattr(req, "priority", None)
    ps = _norm(str(p)) if p is not None else ""
    if ps in {"urgent", "high", "p1", "1"}:
        return 20
    if ps in {"medium", "normal", "p2", "2"}:
        return 10
    if ps in {"low", "p3", "3"}:
        return 4
    return 0


def _score_activity(volunteer: Volunteer) -> int:
    # 0..10
    completed = getattr(volunteer, "completed_count", None)
    if completed is None:
        return 5
    try:
        c = int(completed)
    except Exception:
        return 5
    if c >= 20:
        return 10
    if c >= 5:
        return 8
    if c >= 1:
        return 6
    return 4


def _urgency_multiplier(req: Request) -> float:
    p = getattr(req, "priority", None)
    ps = _norm(str(p)) if p is not None else ""
    if ps in {"urgent", "high", "p1", "1"}:
        return 1.2
    return 1.0


def distance_km(volunteer: Volunteer, req: Request) -> float | None:
    vlat = getattr(volunteer, "latitude", None)
    vlon = getattr(volunteer, "longitude", None)
    rlat = getattr(req, "latitude", None)
    rlon = getattr(req, "longitude", None)
    if vlat is None or vlon is None or rlat is None or rlon is None:
        return None
    try:
        from math import asin, cos, radians, sin, sqrt

        r = 6371.0
        p1, p2 = radians(vlat), radians(rlat)
        dp = radians(rlat - vlat)
        dl = radians(rlon - vlon)
        a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
        return 2 * r * asin(sqrt(a))
    except Exception:
        return None


def _percent(total_score: int, max_score: int = 100) -> int:
    return max(0, min(100, int(round((total_score / max_score) * 100))))


def _now() -> datetime:
    return datetime.utcnow()


def _is_feedback_table_unavailable_error(exc: Exception) -> bool:
    try:
        msg = str(exc).lower()
    except Exception:
        return False
    if "volunteer_match_feedback" in msg and (
        "no such table" in msg or "undefined table" in msg
    ):
        return True
    # Some local SQLite files throw malformed schema errors before table checks.
    return "malformed database schema" in msg


def is_dismissed(volunteer_id: int, request_id: int) -> bool:
    now = _now()
    try:
        row = VolunteerMatchFeedback.query.filter_by(
            volunteer_id=volunteer_id,
            request_id=request_id,
            action="dismissed",
        ).first()
    except (OperationalError, DatabaseError) as exc:
        db.session.rollback()
        if _is_feedback_table_unavailable_error(exc):
            try:
                current_app.logger.warning(
                    "volunteer_match_feedback table missing; is_dismissed fallback=False"
                )
            except Exception:
                pass
            return False
        raise
    if not row or not row.expires_at:
        return False
    return row.expires_at > now


def mark_seen(volunteer_id: int, request_id: int) -> None:
    try:
        row = VolunteerMatchFeedback.query.filter_by(
            volunteer_id=volunteer_id, request_id=request_id
        ).first()
        if not row:
            row = VolunteerMatchFeedback(
                volunteer_id=volunteer_id,
                request_id=request_id,
                action="seen",
                expires_at=None,
            )
            db.session.add(row)
        db.session.commit()
    except (OperationalError, DatabaseError) as exc:
        db.session.rollback()
        if _is_feedback_table_unavailable_error(exc):
            try:
                current_app.logger.warning(
                    "volunteer_match_feedback unavailable; mark_seen no-op"
                )
            except Exception:
                pass
            return
        raise


def dismiss_for(volunteer_id: int, request_id: int, hours: int = 48) -> None:
    try:
        row = VolunteerMatchFeedback.query.filter_by(
            volunteer_id=volunteer_id, request_id=request_id
        ).first()
        if not row:
            row = VolunteerMatchFeedback(
                volunteer_id=volunteer_id,
                request_id=request_id,
                action="dismissed",
                expires_at=_now() + timedelta(hours=hours),
            )
            db.session.add(row)
        else:
            row.action = "dismissed"
            row.expires_at = _now() + timedelta(hours=hours)
        db.session.commit()
    except (OperationalError, DatabaseError) as exc:
        db.session.rollback()
        if _is_feedback_table_unavailable_error(exc):
            try:
                current_app.logger.warning(
                    "volunteer_match_feedback unavailable; dismiss_for no-op"
                )
            except Exception:
                pass
            return
        raise


def _cache_key(
    volunteer: Volunteer,
    limit: int,
    min_percent: int,
    prio: str,
    near: bool,
    max_text_chars: int,
) -> str:
    return "|".join(
        [
            f"v:{getattr(volunteer, 'id', 'x')}",
            f"m:{int(min_percent)}",
            f"l:{int(limit)}",
            f"p:{_norm(prio)}",
            f"n:{1 if near else 0}",
            f"t:{int(max_text_chars)}",
            f"loc:{_norm(getattr(volunteer, 'location', '') or '')}",
            f"sk:{_norm(getattr(volunteer, 'skills', '') or '')[:240]}",
            f"av:{_norm(getattr(volunteer, 'availability', '') or '')}",
        ]
    )


def _cleanup_cache(now_ts: float) -> None:
    if len(_MATCH_CACHE) < 300:
        return
    stale = [k for k, (exp, _) in _MATCH_CACHE.items() if exp <= now_ts]
    for k in stale:
        _MATCH_CACHE.pop(k, None)


def get_matched_requests_v1(
    volunteer: Volunteer,
    limit: int = 12,
    min_percent: int = 55,
    prio: str = "all",
    near: bool = False,
    max_text_chars: int = 800,
    cache_ttl_sec: int = 90,
) -> list[tuple[Request, int, dict]]:
    now_ts = time.time()
    key = _cache_key(
        volunteer=volunteer,
        limit=limit,
        min_percent=min_percent,
        prio=prio,
        near=near,
        max_text_chars=max_text_chars,
    )
    cached = _MATCH_CACHE.get(key)
    if cached and cached[0] > now_ts:
        req_ids = [rid for rid, _, _ in cached[1]]
        req_rows = Request.query.filter(Request.id.in_(req_ids)).all() if req_ids else []
        by_id = {r.id: r for r in req_rows}
        hydrated: list[tuple[Request, int, dict]] = []
        for rid, pct, breakdown in cached[1]:
            r = by_id.get(rid)
            if r is not None:
                hydrated.append((r, pct, dict(breakdown or {})))
        if hydrated:
            return hydrated[: int(limit)]

    q = (
        Request.query.filter(Request.deleted_at.is_(None))
        .filter(Request.is_archived.is_(False))
    )
    now = _now()
    dismiss_filter_applied = False
    try:
        dismissed_ids_subq = (
            db.session.query(VolunteerMatchFeedback.request_id)
            .filter(VolunteerMatchFeedback.volunteer_id == volunteer.id)
            .filter(VolunteerMatchFeedback.action == "dismissed")
            .filter(VolunteerMatchFeedback.expires_at.isnot(None))
            .filter(VolunteerMatchFeedback.expires_at > now)
            .subquery()
        )
        q = q.filter(~Request.id.in_(dismissed_ids_subq))
        dismiss_filter_applied = True
    except (OperationalError, DatabaseError):
        # Backward-compatible fallback while DB is not yet migrated.
        db.session.rollback()
        try:
            current_app.logger.warning(
                "volunteer_match_feedback table missing; continuing without dismiss filter"
            )
        except Exception:
            pass

    vloc = _norm(getattr(volunteer, "location", "") or "")
    if vloc:
        like = f"%{vloc}%"
        conditions = []
        if hasattr(Request, "city"):
            conditions.append(Request.city.ilike(like))
        if hasattr(Request, "region"):
            conditions.append(Request.region.ilike(like))
        if hasattr(Request, "location_text"):
            conditions.append(Request.location_text.ilike(like))
        if conditions:
            q = q.filter(or_(*conditions))

    try:
        candidates = q.order_by(Request.created_at.desc()).limit(200).all()
    except (OperationalError, DatabaseError):
        # Some SQLite setups raise only at execution time.
        db.session.rollback()
        if dismiss_filter_applied:
            q_fallback = (
                Request.query.filter(Request.deleted_at.is_(None))
                .filter(Request.is_archived.is_(False))
            )
            if vloc:
                like = f"%{vloc}%"
                conditions = []
                if hasattr(Request, "city"):
                    conditions.append(Request.city.ilike(like))
                if hasattr(Request, "region"):
                    conditions.append(Request.region.ilike(like))
                if hasattr(Request, "location_text"):
                    conditions.append(Request.location_text.ilike(like))
                if conditions:
                    q_fallback = q_fallback.filter(or_(*conditions))
            candidates = q_fallback.order_by(Request.created_at.desc()).limit(200).all()
            try:
                current_app.logger.warning(
                    "volunteer_match_feedback table missing at execution; fallback without dismiss filter"
                )
            except Exception:
                pass
        else:
            raise
    results: list[tuple[Request, int, dict]] = []
    prio_norm = _norm(prio) or "all"
    for req in candidates:
        s_loc = _score_location(getattr(volunteer, "location", "") or "", req)
        s_sk = _score_skills(volunteer, req, max_text_chars=max_text_chars)
        s_pr = _score_priority(req)
        s_act = _score_activity(volunteer)

        # Priority filter
        req_p = _norm(str(getattr(req, "priority", None) or ""))
        if prio_norm == "urgent" and req_p != "urgent":
            continue
        if prio_norm == "high" and req_p not in {"urgent", "high"}:
            continue

        # Near filter (25km default)
        dkm = distance_km(volunteer, req)
        if near:
            if dkm is None or dkm > 25:
                continue

        raw = s_loc + s_sk + s_pr + s_act
        u_mult = _urgency_multiplier(req)
        raw = int(round(raw * u_mult))
        pct = _percent(raw, 100)
        if pct < int(min_percent):
            continue

        breakdown = {
            "loc": s_loc,
            "city": s_loc,
            "skills": s_sk,
            "priority": s_pr,
            "activity": s_act,
            "distance": int(round(dkm)) if dkm is not None else 0,
            "urgent": (s_pr >= 20),
            "urgency_mult": round(u_mult, 2),
        }
        results.append((req, pct, breakdown))

    results.sort(
        key=lambda t: (
            t[1],
            1 if t[2].get("urgent") else 0,
            getattr(t[0], "created_at", None) or datetime.min,
        ),
        reverse=True,
    )
    final = results[: int(limit)]
    _cleanup_cache(now_ts)
    _MATCH_CACHE[key] = (
        now_ts + int(cache_ttl_sec),
        [(r.id, int(p), dict(b or {})) for (r, p, b) in final],
    )
    return final
