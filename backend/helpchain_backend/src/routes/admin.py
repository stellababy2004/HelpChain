from __future__ import annotations

import csv
import json
import math
import secrets
import time
from datetime import UTC, datetime, timedelta, timezone
from functools import wraps
from io import BytesIO, StringIO
from typing import Optional
from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from backend.audit import log_activity
from backend.extensions import db, limiter
from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest
from backend.helpchain_backend.src.statuses import (
    REQUEST_STATUS_ALLOWED,
    normalize_request_status,
)

from ..config import Config
from ..models import (
    AdminUser,
    ActivityLog,
    Notification,
    ProAccessRequest,
    ProfessionalLead,
    Request,
    RequestActivity,
    RequestLog,
    RequestMetric,
    Volunteer,
    VolunteerAction,
    VolunteerInterest,
    VolunteerRequestState,
    utc_now,
)
from ..notifications.inapp import NUDGE_COOLDOWN_HOURS, send_nudge_notification
from ..security_logging import log_security_event

INVALID_CREDENTIALS_MSG = "Invalid credentials."
CLOSED_STATUSES = {"done", "cancelled", "rejected"}
ASSIGN_SLA_HOURS = 48
RESOLVE_SLA_DAYS = 7
VOLUNTEER_ASSIGN_SLA_HOURS = 72
NOTSEEN_TIERS_HOURS = (24, 48, 72)
PRO_ACCESS_STATUSES = ("new", "reviewed", "approved", "rejected")
_SCHEMA_COLUMN_CACHE: dict[tuple[str, str], bool] = {}


def _table_has_column(table_name: str, column_name: str) -> bool:
    key = (table_name, column_name)
    cached = _SCHEMA_COLUMN_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        inspector = sa_inspect(db.session.get_bind())
        exists = any(
            col.get("name") == column_name for col in inspector.get_columns(table_name)
        )
    except Exception:
        exists = False
    _SCHEMA_COLUMN_CACHE[key] = exists
    return exists


def _log_status_change_once(
    req_id: int,
    old_status: str | None,
    new_status: str | None,
    actor_admin_id: int | None,
):
    """Add a single status_change activity only when there is a real change."""
    if not _table_has_column("request_activities", "volunteer_id"):
        return
    if (old_status or "") == (new_status or ""):
        return
    db.session.add(
        RequestActivity(
            request_id=req_id,
            actor_admin_id=actor_admin_id,
            action="status_change",
            old_value=old_status,
            new_value=new_status,
        )
    )


def _is_request_locked(req) -> bool:
    """Consider a request locked when status is done or cancelled (canonical)."""
    s = normalize_request_status(getattr(req, "status", None))
    return s in ("done", "cancelled")


def _now_utc():
    return datetime.now(UTC)


def _engagement_label(score: int) -> str:
    if score >= 5:
        return "High"
    if score >= 1:
        return "Medium"
    return "At risk"


def get_volunteer_engagement_score(volunteer_id: int, now: datetime | None = None) -> dict:
    """
    Heuristic engagement score per volunteer in range [-10..+10].
    """
    now = now or datetime.utcnow()
    cutoff_72h = now - timedelta(hours=72)

    seen_within_24h = 0
    not_seen_72h = 0
    has_vrs_notified_at = _table_has_column("volunteer_request_states", "notified_at")
    if has_vrs_notified_at:
        states = (
            db.session.query(
                VolunteerRequestState.notified_at,
                VolunteerRequestState.seen_at,
            )
            .filter(VolunteerRequestState.volunteer_id == volunteer_id)
            .filter(VolunteerRequestState.notified_at.isnot(None))
            .all()
        )
        for notified_at, seen_at in states:
            if notified_at is None:
                continue
            if seen_at is not None and seen_at <= (notified_at + timedelta(hours=24)):
                seen_within_24h += 1
            if seen_at is None and notified_at <= cutoff_72h:
                not_seen_72h += 1
    else:
        # Compatibility fallback for environments where notified_at migration is missing.
        notif_rows = (
            db.session.query(Notification.created_at, Notification.read_at, Notification.is_read)
            .filter(Notification.volunteer_id == volunteer_id)
            .filter(Notification.type == "new_match")
            .all()
        )
        for created_at, read_at, is_read in notif_rows:
            if created_at is None:
                continue
            if read_at is not None and read_at <= (created_at + timedelta(hours=24)):
                seen_within_24h += 1
            if (not bool(is_read)) and created_at <= cutoff_72h:
                not_seen_72h += 1

    can_help = 0
    cant_help = 0
    if _table_has_column("request_activities", "volunteer_id"):
        can_help = (
            db.session.query(func.count(RequestActivity.id))
            .filter(RequestActivity.volunteer_id == volunteer_id)
            .filter(RequestActivity.action == "volunteer_can_help")
            .scalar()
            or 0
        )
        cant_help = (
            db.session.query(func.count(RequestActivity.id))
            .filter(RequestActivity.volunteer_id == volunteer_id)
            .filter(RequestActivity.action == "volunteer_cant_help")
            .scalar()
            or 0
        )

    raw_score = (
        2 * int(seen_within_24h)
        + 3 * int(can_help)
        - 1 * int(cant_help)
        - 3 * int(not_seen_72h)
    )
    score = max(-10, min(10, int(raw_score)))
    return {
        "volunteer_id": int(volunteer_id),
        "score": score,
        "label": _engagement_label(score),
        "seen_within_24h": int(seen_within_24h),
        "not_seen_72h": int(not_seen_72h),
        "can_help": int(can_help),
        "cant_help": int(cant_help),
    }


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _delta_seconds(start: datetime | None, end: datetime | None) -> int | None:
    start_n = _to_utc_naive(start)
    end_n = _to_utc_naive(end)
    if not start_n or not end_n:
        return None
    return max(0, int((end_n - start_n).total_seconds()))


def compute_response_metrics(
    request_id: int, sla_hours: int = 12, now: datetime | None = None
) -> dict:
    """
    Compute response metrics for a request using assigned volunteer context.
    """
    now_naive = _to_utc_naive(now) or datetime.utcnow()
    out = {
        "request_id": int(request_id),
        "assigned_volunteer_id": None,
        "first_seen_seconds": None,
        "first_action_seconds": None,
        "assignment_delay_seconds": None,
        "not_seen_after_24h": False,
        "sla_hours": int(sla_hours),
        "sla_under_threshold": None,
        "sla_bucket": "no_assignee",
    }

    req = (
        db.session.query(Request.id, Request.created_at, Request.assigned_volunteer_id)
        .filter(Request.id == request_id)
        .first()
    )
    if not req:
        out["sla_bucket"] = "missing_request"
        return out

    req_created_at = _to_utc_naive(getattr(req, "created_at", None))
    assigned_volunteer_id = getattr(req, "assigned_volunteer_id", None)
    out["assigned_volunteer_id"] = assigned_volunteer_id

    first_assign_at = (
        db.session.query(func.min(RequestActivity.created_at))
        .filter(RequestActivity.request_id == request_id)
        .filter(RequestActivity.action == "assign_volunteer")
        .scalar()
    )
    out["assignment_delay_seconds"] = _delta_seconds(req_created_at, first_assign_at)

    if not assigned_volunteer_id:
        return out

    state = (
        db.session.query(VolunteerRequestState.notified_at, VolunteerRequestState.seen_at)
        .filter(VolunteerRequestState.request_id == request_id)
        .filter(VolunteerRequestState.volunteer_id == int(assigned_volunteer_id))
        .first()
    )
    notified_at = _to_utc_naive(state[0]) if state else None
    seen_at = _to_utc_naive(state[1]) if state else None

    out["first_seen_seconds"] = _delta_seconds(notified_at, seen_at)
    out["not_seen_after_24h"] = bool(
        notified_at
        and not seen_at
        and ((now_naive - notified_at).total_seconds() >= 24 * 3600)
    )

    action_q = (
        db.session.query(func.min(RequestActivity.created_at))
        .filter(RequestActivity.request_id == request_id)
        .filter(
            RequestActivity.action.in_(["volunteer_can_help", "volunteer_cant_help"])
        )
    )
    if _table_has_column("request_activities", "volunteer_id"):
        action_q = action_q.filter(
            RequestActivity.volunteer_id == int(assigned_volunteer_id)
        )
    if notified_at is not None:
        action_q = action_q.filter(RequestActivity.created_at >= notified_at)
    first_action_at = action_q.scalar()
    out["first_action_seconds"] = _delta_seconds(notified_at, first_action_at)

    if notified_at is None:
        out["sla_bucket"] = "no_notification"
        return out
    if out["first_action_seconds"] is None:
        out["sla_bucket"] = "no_action"
        return out

    sla_seconds = int(sla_hours) * 3600
    under = out["first_action_seconds"] <= sla_seconds
    out["sla_under_threshold"] = bool(under)
    out["sla_bucket"] = "under_sla" if under else "over_sla"
    return out


def _notseen_hours_from_risk(risk: str) -> int | None:
    if risk == "notseen":
        return 24
    if not risk.startswith("notseen"):
        return None
    suffix = risk[len("notseen") :]
    if not suffix.isdigit():
        return None
    hours = int(suffix)
    if hours in NOTSEEN_TIERS_HOURS:
        return hours
    return None


def _build_notseen_subquery(now: datetime, *, hours: int):
    cutoff = now - timedelta(hours=hours)
    has_vrs_notified_at = _table_has_column("volunteer_request_states", "notified_at")
    if has_vrs_notified_at:
        subq = (
            db.session.query(VolunteerRequestState.request_id)
            .filter(VolunteerRequestState.notified_at.isnot(None))
            .filter(VolunteerRequestState.notified_at < cutoff)
            .filter(VolunteerRequestState.seen_at.is_(None))
            .subquery()
        )
        source = "notified_at"
    else:
        subq = (
            db.session.query(Notification.request_id)
            .filter(Notification.type == "new_match")
            .filter(Notification.created_at < cutoff)
            .subquery()
        )
        source = "notification_created_at_fallback"
    return subq, source


def _admin_id():
    return getattr(current_user, "id", None)


LOCK_TTL_MINUTES = 30


def _lock_expired(req, now: datetime | None = None) -> bool:
    """Return True if owned_at is older than LOCK_TTL_MINUTES."""
    now = now or _now_utc()
    owned_at = getattr(req, "owned_at", None)
    if not owned_at:
        return False
    try:
        if owned_at.tzinfo is None:
            owned_at = owned_at.replace(tzinfo=UTC)
        return (now - owned_at).total_seconds() > LOCK_TTL_MINUTES * 60
    except Exception:
        return False


def _locked_by_other(req, admin_id, now: datetime | None = None) -> bool:
    return bool(
        getattr(req, "owner_id", None)
        and getattr(req, "owner_id", None) != admin_id
        and not _lock_expired(req, now or _now_utc())
    )


from sqlalchemy import case, func, inspect as sa_inspect, or_
from sqlalchemy.orm import joinedload

from backend.helpchain_backend.src.utils.mfa import (
    build_totp_uri,
    generate_totp_secret,
    qr_png_base64,
    verify_totp_code,
)

admin_bp = Blueprint(
    "admin", __name__, url_prefix="/admin"
)  # single templates path via app.py


@admin_bp.before_request
def require_admin_session():
    """
    Gate the entire /admin surface behind the explicit admin session flag.

    Security/UX:
    - No public access to admin pages (redirect to login).
    - "Admin" navbar link is also keyed off the same session flag.
    """
    allowed = {
        "admin.ops_login",
        "admin.admin_login_legacy",
    }
    if request.endpoint in allowed or (
        request.endpoint and request.endpoint.startswith("static")
    ):
        return None

    if session.get("admin_logged_in"):
        return None

    nxt = request.full_path if request.query_string else request.path
    return redirect(url_for("admin.ops_login", next=nxt), code=303)


@admin_bp.get("/")
def admin_index():
    """Redirect bare /admin to the main requests list."""
    return redirect(url_for("admin.admin_requests"))


@admin_bp.get("/dashboard")
def admin_dashboard_redirect():
    """Alias for /admin/requests to avoid 404s from legacy /admin/dashboard links."""
    return redirect(url_for("admin.admin_requests"))


def admin_required_404():
    if not (current_user.is_authenticated and getattr(current_user, "is_admin", False)):
        abort(404)


def _is_local_request() -> bool:
    """True when request comes from localhost (IPv4/IPv6)."""
    return request.remote_addr in ("127.0.0.1", "::1")


def is_safe_url(target: str) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (test_url.scheme in ("http", "https")) and (
        ref_url.netloc == test_url.netloc
    )


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        # Harden: hide admin surface from non-admins (404 instead of redirect)
        if not (
            current_user.is_authenticated and getattr(current_user, "is_admin", False)
        ):
            abort(404)
        return view_func(*args, **kwargs)

    return wrapper


def log_request_activity(req_obj, action, old=None, new=None, actor_admin_id=None):
    """Append a RequestActivity row; swallow errors so UI flows stay smooth."""
    if not _table_has_column("request_activities", "volunteer_id"):
        return
    try:
        actor_id = actor_admin_id
        if actor_id is None and getattr(current_user, "is_authenticated", False):
            actor_id = getattr(current_user, "id", None)
        activity = RequestActivity(
            request_id=getattr(req_obj, "id", req_obj),
            actor_admin_id=actor_id,
            action=action,
            old_value=str(old) if old is not None else None,
            new_value=str(new) if new is not None else None,
            created_at=utc_now(),
        )
        db.session.add(activity)
    except Exception:
        pass


def _audit_request(
    req_id: int,
    *,
    action: str,
    message: str | None = None,
    old: str | None = None,
    new: str | None = None,
    meta: dict | None = None,
):
    if not _table_has_column("activity_logs", "id"):
        return
    try:
        log_activity(
            entity_type="request",
            entity_id=req_id,
            action=action,
            message=message,
            old_value=str(old) if old is not None else None,
            new_value=str(new) if new is not None else None,
            meta=meta,
        )
    except Exception:
        pass


def _audit_pro_access(
    pro_id: int,
    *,
    action: str,
    message: str | None = None,
    old: str | None = None,
    new: str | None = None,
    meta: dict | None = None,
):
    if not _table_has_column("activity_logs", "id"):
        return
    try:
        log_activity(
            entity_type="pro_access",
            entity_id=pro_id,
            action=action,
            message=message,
            old_value=str(old) if old is not None else None,
            new_value=str(new) if new is not None else None,
            meta=meta,
        )
    except Exception:
        pass


def _mfa_ok_set(ttl_min: int | None = None):
    ttl = ttl_min or current_app.config.get("MFA_SESSION_TTL_MIN", 720)
    session[current_app.config.get("MFA_SESSION_KEY", "mfa_ok")] = True
    try:
        session["mfa_ok_until"] = (utc_now() + timedelta(minutes=ttl)).isoformat()
    except Exception:
        session["mfa_ok_until"] = None


def _mfa_ok_clear():
    session.pop(current_app.config.get("MFA_SESSION_KEY", "mfa_ok"), None)
    session.pop("mfa_ok_until", None)


def _mfa_ok_is_valid() -> bool:
    if not session.get(current_app.config.get("MFA_SESSION_KEY", "mfa_ok")):
        return False
    until = session.get("mfa_ok_until")
    if not until:
        return False
    try:
        return utc_now() <= datetime.fromisoformat(until)
    except Exception:
        return False


def _mfa_lock_is_active() -> tuple[bool, int]:
    lock_until = session.get("mfa_lock_until")
    if not lock_until:
        return (False, 0)
    try:
        dt = datetime.fromisoformat(lock_until)
        if utc_now() >= dt:
            session.pop("mfa_lock_until", None)
            session.pop("mfa_attempts", None)
            return (False, 0)
        return (True, int((dt - utc_now()).total_seconds()))
    except Exception:
        session.pop("mfa_lock_until", None)
        session.pop("mfa_attempts", None)
        return (False, 0)


def _mfa_attempt_fail():
    max_attempts = current_app.config.get("MFA_VERIFY_MAX_ATTEMPTS", 8)
    lock_min = current_app.config.get("MFA_VERIFY_LOCK_MIN", 10)
    session["mfa_attempts"] = int(session.get("mfa_attempts", 0)) + 1
    if session["mfa_attempts"] >= max_attempts:
        try:
            session["mfa_lock_until"] = (
                utc_now() + timedelta(minutes=lock_min)
            ).isoformat()
        except Exception:
            session["mfa_lock_until"] = None


def _mfa_attempt_reset():
    session.pop("mfa_attempts", None)
    session.pop("mfa_lock_until", None)


def _generate_backup_codes(n: int = 10) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codes = []
    for _ in range(n):
        code = "".join(secrets.choice(alphabet) for _ in range(10))
        codes.append(code)
    return codes


def _hash_codes(codes: list[str]) -> list[str]:
    return [generate_password_hash(c) for c in codes]


def _load_hashes(user) -> list[str]:
    raw = getattr(user, "backup_codes_hashes", None)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _save_hashes(user, hashes: list[str]):
    user.backup_codes_hashes = json.dumps(hashes)
    user.backup_codes_generated_at = utc_now()
    db.session.commit()


def can_edit_request(req_obj, user) -> bool:
    """Owner or super_admin can edit; if no owner, only super_admin."""
    if getattr(user, "role", None) == "super_admin":
        return True
    owner_id = getattr(req_obj, "owner_id", None)
    user_id = getattr(user, "id", None)
    return owner_id is not None and owner_id == user_id


def is_stale(req_obj, minutes: int = 30) -> bool:
    """Return True if owned_at is older than `minutes`."""
    owned_at = getattr(req_obj, "owned_at", None)
    if not owned_at:
        return False
    try:
        return (utc_now() - owned_at).total_seconds() > minutes * 60
    except Exception:
        return False


@admin_bp.before_request
def enforce_admin_mfa():
    if not current_app.config.get("MFA_ENABLED", False):
        return None
    allowed = {
        "admin.ops_login",
        "admin.admin_login_legacy",
        "admin.admin_logout",
        "admin.admin_mfa_setup",
        "admin.admin_mfa_verify",
        "admin.admin_mfa_backup_codes",
        "static",
    }
    if request.endpoint in allowed or (
        request.endpoint and request.endpoint.startswith("static")
    ):
        return None
    if not current_user.is_authenticated:
        return None
    if not (
        getattr(current_user, "mfa_enabled", False)
        and getattr(current_user, "totp_secret", None)
    ):
        return None
    if _mfa_ok_is_valid():
        return None
    nxt = request.full_path if request.query_string else request.path
    return redirect(url_for("admin.admin_mfa_verify", next=nxt))


@admin_bp.route("/emergency-requests", methods=["GET"])
@admin_required
def emergency_requests():
    admin_required_404()
    # Admin guard (same as admin_dashboard)
    if not getattr(current_user, "is_admin", False):
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    q = (request.args.get("q") or "").strip()
    days = int(request.args.get("days") or 7)
    days = max(1, min(days, 90))
    page = int(request.args.get("page") or 1)
    page = max(page, 1)
    per_page = int(request.args.get("per_page") or 25)
    per_page = max(10, min(per_page, 100))
    since = datetime.utcnow() - timedelta(days=days)

    # Emergency filter: category=="emergency" only (no urgency field)
    query = Request.query.filter(
        Request.created_at >= since, Request.category == "emergency"
    ).order_by(Request.created_at.desc())

    if q:
        # Search in city/contact/priority only
        query = query.filter(
            (Request.city.ilike(f"%{q}%"))
            | (Request.email.ilike(f"%{q}%"))
            | (Request.phone.ilike(f"%{q}%"))
            | (Request.priority.ilike(f"%{q}%"))
        )

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return render_template(
        "admin_emergency_requests.html",
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        q=q,
        days=days,
    )


# API endpoint за заявки с филтри (status, date)
def api_requests():
    from flask import current_app, jsonify, request

    # During tests we allow access to the API endpoints to simplify fixtures
    if not current_app.config.get("TESTING", False):
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Unauthorized"}), 403
    query = Request.query
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    if status:
        query = query.filter_by(status=status)
    if date_from:
        try:
            from datetime import datetime

            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(Request.created_at >= date_from_dt)
        except Exception:
            pass
    if date_to:
        try:
            from datetime import datetime, timedelta

            date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.filter(Request.created_at < date_to_dt)
        except Exception:
            pass
    requests = query.order_by(Request.created_at.desc()).all()
    data = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in requests
    ]
    return jsonify({"items": data})


# API endpoint за всички доброволци (JSON)
def api_volunteers():
    from flask import current_app, jsonify

    if not current_app.config.get("TESTING", False):
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Unauthorized"}), 403
    volunteers = Volunteer.query.all()
    data = [
        {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "location": v.location,
            "skills": v.skills,
            "is_active": v.is_active,
        }
        for v in volunteers
    ]
    return jsonify(data)


# Детайли за доброволец
@admin_bp.route("/admin_volunteers/<int:id>")
@admin_required
def volunteer_detail(id):
    admin_required_404()
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))
    from flask import abort

    volunteer = db.session.get(Volunteer, id)
    if not volunteer:
        abort(404)
    return render_template("volunteer_detail.html", volunteer=volunteer)


@admin_bp.get("/api/volunteers/<int:vol_id>")
@admin_required
def admin_volunteer_api(vol_id: int):
    admin_required_404()
    volunteer = db.session.get(Volunteer, vol_id)
    if not volunteer:
        abort(404)
    req_id_raw = (request.args.get("req_id") or "").strip()
    req_id = int(req_id_raw) if req_id_raw.isdigit() else None

    def _to_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        raw = str(value).strip()
        if not raw:
            return []
        return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]

    last_active = getattr(volunteer, "last_activity", None) or getattr(
        volunteer, "updated_at", None
    )
    can_help_count = (
        db.session.query(func.count(VolunteerAction.id))
        .filter(
            VolunteerAction.volunteer_id == volunteer.id,
            VolunteerAction.action == "CAN_HELP",
        )
        .scalar()
        or 0
    )
    action_rows = (
        VolunteerAction.query.filter_by(volunteer_id=volunteer.id)
        .order_by(VolunteerAction.updated_at.desc())
        .limit(5)
        .all()
    )
    history = [
        {
            "request_id": row.request_id,
            "action": row.action,
            "at": (
                (row.updated_at or row.created_at).isoformat(
                    sep=" ", timespec="minutes"
                )
                if (row.updated_at or row.created_at)
                else None
            ),
        }
        for row in action_rows
    ]

    notified_at = None
    seen_at = None
    if req_id is not None:
        notif = (
            Notification.query.filter_by(
                volunteer_id=volunteer.id, type="new_match", request_id=req_id
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        if notif:
            notified_at = (
                notif.created_at.isoformat(sep=" ", timespec="minutes")
                if notif.created_at
                else None
            )
            seen_at = (
                notif.read_at.isoformat(sep=" ", timespec="minutes")
                if notif.read_at
                else None
            )

    data = {
        "id": volunteer.id,
        "name": getattr(volunteer, "name", None) or f"Volunteer #{volunteer.id}",
        "email": getattr(volunteer, "email", None),
        "phone": getattr(volunteer, "phone", None),
        "city": None,
        "location": getattr(volunteer, "location", None),
        "languages": [],
        "roles": _to_list(getattr(volunteer, "skills", None)),
        "availability": getattr(volunteer, "availability", None),
        "last_active": (
            last_active.isoformat(sep=" ", timespec="minutes") if last_active else None
        ),
        "can_help_count": int(can_help_count),
        "history": history,
        "notified_at": notified_at,
        "seen_at": seen_at,
        "profile_url": url_for("admin.volunteer_detail", id=volunteer.id),
    }
    return jsonify(data)


@admin_bp.route("/ops/login", methods=["GET", "POST"], endpoint="ops_login")
@limiter.limit("5 per 5 minutes")
@limiter.limit("20 per hour")
def admin_ops_login():
    # Preserve safe next across GET -> POST -> redirect (and across failed logins).
    next_candidate = (
        request.form.get("next") or request.args.get("next") or ""
    ).strip()
    next_url = next_candidate if is_safe_url(next_candidate) else ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = AdminUser.query.filter_by(username=username).first()
        if (
            not user
            or not getattr(user, "password_hash", None)
            or not check_password_hash(user.password_hash, password)
        ):
            log_security_event(
                "auth_admin_login_failed",
                actor_type="anonymous",
                meta={"reason": "invalid_credentials"},
            )
            flash(INVALID_CREDENTIALS_MSG, "danger")
            return redirect(url_for("admin.ops_login", next=next_url))
        # Successful login path
        session.clear()  # mitigate session fixation
        login_user(user, remember=False)
        session["admin_user_id"] = user.id
        session["admin_logged_in"] = True
        log_activity(
            entity_type="admin",
            entity_id=user.id,
            action="admin_login",
            message="Admin login",
            meta={"via": "admin_ops_login"},
            persist=True,
        )
        log_security_event(
            "auth_admin_login_success",
            actor_type="admin",
            actor_id=user.id,
        )
        # MFA flow
        session.pop(Config.MFA_SESSION_KEY, None)
        session.pop("mfa_required", None)
        mfa_globally_enabled = bool(Config.MFA_ENABLED)
        user_has_mfa = bool(getattr(user, "mfa_enabled", False)) and bool(
            getattr(user, "totp_secret", None)
        )
        if mfa_globally_enabled and user_has_mfa:
            session["mfa_required"] = True
            return redirect(
                url_for(
                    "admin.admin_mfa_verify",
                    next=next_url or url_for("admin.admin_requests"),
                )
            )
        _mfa_ok_set()
        return redirect(next_url or url_for("admin.admin_requests"), code=303)
    return render_template("admin/login.html", next=next_url)


@admin_bp.get("/login")
@limiter.limit("30 per minute")
def admin_login_legacy():
    """Legacy alias to ops login; preserves ?next=."""
    nxt = request.args.get("next", "")
    return redirect(url_for("admin.ops_login", next=nxt))


@admin_bp.route("/logout", methods=["GET", "POST"])
def admin_logout():
    admin_required_404()
    actor_id = getattr(current_user, "id", 0) or 0
    log_activity(
        entity_type="admin",
        entity_id=actor_id,
        action="admin_logout",
        message="Admin logout",
        persist=True,
    )
    _mfa_ok_clear()
    _mfa_attempt_reset()
    session.pop("mfa_required", None)
    session.pop("mfa_pending_secret", None)
    session.pop("backup_codes_plain", None)
    session.pop("admin_user_id", None)
    session.pop("admin_logged_in", None)
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("admin.ops_login"))


MFA_PENDING_SECRET_KEY = "mfa_pending_secret"
MFA_SESSION_KEY = "mfa_ok"


@admin_bp.route("/mfa/setup", methods=["GET", "POST"])
@login_required
def admin_mfa_setup():
    admin_required_404()
    if getattr(current_user, "mfa_enabled", False) and getattr(
        current_user, "totp_secret", None
    ):
        flash("MFA вече е активиран.", "info")
        return redirect(url_for("admin.admin_mfa_verify"))

    pending_secret = session.get(MFA_PENDING_SECRET_KEY)
    if not pending_secret:
        pending_secret = generate_totp_secret()
        session[MFA_PENDING_SECRET_KEY] = pending_secret

    issuer = "HelpChain"
    username = getattr(current_user, "username", f"admin-{current_user.id}")
    uri = build_totp_uri(pending_secret, username=username, issuer=issuer)
    qr_b64 = qr_png_base64(uri)

    if request.method == "POST":
        code = (request.form.get("code") or "").strip().replace(" ", "")
        if not code:
            flash("Въведи 6-цифрения код от приложението.", "danger")
            return render_template(
                "admin/mfa_setup.html",
                qr_b64=qr_b64,
                secret=pending_secret,
                username=username,
            )

        if not verify_totp_code(pending_secret, code):
            flash(
                "Невалиден код. Провери часовника на телефона и опитай пак.", "danger"
            )
            return render_template(
                "admin/mfa_setup.html",
                qr_b64=qr_b64,
                secret=pending_secret,
                username=username,
            )

        user = db.session.get(AdminUser, current_user.id)
        user.totp_secret = pending_secret
        user.mfa_enabled = True
        user.mfa_enrolled_at = utc_now()
        db.session.commit()

        _mfa_ok_set()
        session.pop(MFA_PENDING_SECRET_KEY, None)
        flash("✅ MFA е активиран успешно.", "success")
        flash("Сега си генерирай backup codes (спасителният пояс).", "info")
        return redirect(url_for("admin.admin_mfa_backup_codes"))

    return render_template(
        "admin/mfa_setup.html", qr_b64=qr_b64, secret=pending_secret, username=username
    )


@admin_bp.route("/mfa/verify", methods=["GET", "POST"])
@login_required
def admin_mfa_verify():
    admin_required_404()
    if not current_app.config.get("MFA_ENABLED", False):
        abort(404)

    if not (
        getattr(current_user, "mfa_enabled", False)
        and getattr(current_user, "totp_secret", None)
    ):
        _mfa_ok_set()
        session["admin_logged_in"] = True
        return redirect(request.args.get("next") or url_for("admin.admin_requests"))

    locked, remaining = _mfa_lock_is_active()
    if request.method == "GET":
        return render_template(
            "admin/mfa_verify.html",
            locked=locked,
            remaining=remaining,
            next=request.args.get("next") or "",
        )

    if locked:
        flash(
            f"Твърде много опити. Опитай след {max(1, remaining // 60)} мин.", "danger"
        )
        return redirect(
            url_for("admin.admin_mfa_verify", next=request.args.get("next", ""))
        )

    code = (request.form.get("code") or "").strip().replace(" ", "").upper()
    totp_ok = False
    try:
        totp_ok = verify_totp_code(current_user.totp_secret, code)
    except Exception:
        totp_ok = False

    backup_ok = False
    if not totp_ok:
        hashes = _load_hashes(current_user)
        for i, h in enumerate(hashes):
            if check_password_hash(h, code):
                backup_ok = True
                hashes.pop(i)
                _save_hashes(current_user, hashes)
                break

    if totp_ok or backup_ok:
        _mfa_attempt_reset()
        _mfa_ok_set()
        session["admin_logged_in"] = True
        log_activity(
            entity_type="admin",
            entity_id=getattr(current_user, "id", 0) or 0,
            action="admin_mfa_success",
            message="Admin MFA verified",
            persist=True,
        )
        flash("✅ MFA потвърдено.", "success")
        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect(url_for("admin.admin_requests"))

    _mfa_attempt_fail()
    locked, remaining = _mfa_lock_is_active()
    if locked:
        flash(f"Грешен код. Заключено за ~{max(1, remaining // 60)} мин.", "danger")
    else:
        left = current_app.config.get("MFA_VERIFY_MAX_ATTEMPTS", 8) - int(
            session.get("mfa_attempts", 0)
        )
        flash(f"Грешен код. Оставащи опити: {max(left, 0)}.", "danger")

    return redirect(
        url_for("admin.admin_mfa_verify", next=request.args.get("next", ""))
    )


@admin_bp.route("/mfa/backup-codes", methods=["GET", "POST"])
@login_required
def admin_mfa_backup_codes():
    admin_required_404()
    if not current_app.config.get("MFA_ENABLED", False):
        abort(404)
    if not (
        getattr(current_user, "mfa_enabled", False)
        and getattr(current_user, "totp_secret", None)
    ):
        flash("Първо активирай MFA от Setup.", "warning")
        return redirect(url_for("admin.admin_mfa_setup"))

    if request.method == "POST":
        codes = _generate_backup_codes(10)
        _save_hashes(current_user, _hash_codes(codes))
        session["backup_codes_plain"] = codes
        flash(
            "Backup кодовете са генерирани. Запази ги сега — няма да се покажат втори път.",
            "success",
        )
        return redirect(url_for("admin.admin_mfa_backup_codes"))

    codes_plain = session.pop("backup_codes_plain", None)
    hashes = _load_hashes(current_user)
    has_codes = len(hashes) > 0
    return render_template(
        "admin/mfa_backup_codes.html",
        codes=codes_plain,
        has_codes=has_codes,
        generated_at=getattr(current_user, "backup_codes_generated_at", None),
    )


@admin_bp.route("/2fa", methods=["GET", "POST"])
@admin_required
def admin_2fa():
    admin_required_404()
    """2FA верификация за админ"""
    user_id = session.get("pending_admin_user_id")
    if not user_id:
        return redirect(url_for("admin.ops_login"))

    admin_user = db.session.get(AdminUser, user_id)
    if not admin_user:
        return redirect(url_for("admin.ops_login"))

    if request.method == "POST":
        token = request.form.get("token")
        if admin_user.verify_totp(token):
            from flask_login import login_user

            login_user(admin_user)
            session.pop("pending_admin_user_id", None)
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Невалиден 2FA код.", "error")

    return render_template("admin_2fa.html")


@admin_bp.route("/2fa/setup", methods=["GET", "POST"])
@admin_required
def admin_2fa_setup():
    admin_required_404()
    """Настройка на 2FA за админ"""
    if not isinstance(current_user, AdminUser):
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        token = request.form.get("token")
        if current_user.verify_totp(token):
            current_user.enable_2fa()
            flash("2FA е активиран успешно!", "success")
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Невалиден код.", "error")

    uri = current_user.get_totp_uri()
    return render_template("admin_2fa_setup.html", totp_uri=uri)


@admin_bp.route("/2fa/disable", methods=["POST"])
@admin_required
def admin_2fa_disable():
    admin_required_404()
    """Деактивиране на 2FA за админ"""
    if not isinstance(current_user, AdminUser):
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    current_user.disable_2fa()
    flash("2FA е деактивиран.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.get("/api/dashboard")
@login_required
def admin_api_dashboard():
    admin_required_404()
    """Session-based dashboard data for admin UI (bypass JWT)."""
    if not getattr(current_user, "is_admin", False):
        return jsonify({"error": "forbidden"}), 403

    try:
        try:
            days = int(request.args.get("days", 30))
        except Exception:
            days = 30

        since_dt = datetime.utcnow() - timedelta(days=days)

        status_rows = (
            db.session.query(
                func.coalesce(Request.status, "unknown").label("status"),
                func.count(Request.id).label("cnt"),
            )
            .group_by("status")
            .all()
        )
        counts_by_status = {status: int(cnt) for status, cnt in status_rows}
        total_requests = int(sum(counts_by_status.values()))

        city_expr = func.coalesce(
            func.nullif(Request.city, ""),
            func.nullif(Request.region, ""),
            "unknown",
        )
        city_rows = (
            db.session.query(
                city_expr.label("city"), func.count(Request.id).label("cnt")
            )
            .group_by("city")
            .order_by(func.count(Request.id).desc())
            .limit(10)
            .all()
        )
        requests_by_city = [{"city": c, "count": int(cnt)} for c, cnt in city_rows]

        ts_rows = (
            db.session.query(
                func.date(Request.created_at).label("day"),
                func.count(Request.id).label("cnt"),
            )
            .filter(Request.created_at.isnot(None))
            .filter(Request.created_at >= since_dt)
            .group_by("day")
            .order_by("day")
            .all()
        )
        timeseries = [{"date": str(day), "count": int(cnt)} for day, cnt in ts_rows]

        try:
            total_volunteers = db.session.query(Volunteer).count()
        except Exception:
            total_volunteers = 0

        return (
            jsonify(
                {
                    "total_requests": total_requests,
                    "total_volunteers": total_volunteers,
                    "counts_by_status": counts_by_status,
                    "requests_by_city": requests_by_city,
                    "timeseries": timeseries,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


SLA_HOURS_DEFAULT = 12


def _pctl(values, p: float = 0.9) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    vals.sort()
    idx = max(0, min(len(vals) - 1, math.ceil(p * len(vals)) - 1))
    return float(vals[idx])


def _sla_outliers_action_7d(first_action_subq, now: datetime, limit: int = 5) -> list[dict]:
    cutoff = now - timedelta(days=7)
    delay_expr = func.strftime(
        "%s", first_action_subq.c.first_action_at
    ) - func.strftime("%s", VolunteerRequestState.notified_at)
    rows = (
        db.session.query(
            VolunteerRequestState.request_id.label("request_id"),
            VolunteerRequestState.volunteer_id.label("volunteer_id"),
            VolunteerRequestState.notified_at.label("notified_at"),
            first_action_subq.c.first_action_at.label("first_action_at"),
            delay_expr.label("delay_seconds"),
        )
        .join(
            first_action_subq,
            (first_action_subq.c.req_id == VolunteerRequestState.request_id)
            & (first_action_subq.c.vol_id == VolunteerRequestState.volunteer_id),
        )
        .filter(VolunteerRequestState.notified_at.isnot(None))
        .filter(VolunteerRequestState.notified_at >= cutoff)
        .filter(first_action_subq.c.first_action_at.isnot(None))
        .filter(first_action_subq.c.first_action_at >= cutoff)
        .filter(delay_expr >= 0)
        .order_by(db.text("delay_seconds DESC"))
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        out.append(
            {
                "request_id": int(row.request_id),
                "volunteer_id": (
                    int(row.volunteer_id) if row.volunteer_id is not None else None
                ),
                "delay_seconds": (
                    float(row.delay_seconds) if row.delay_seconds is not None else None
                ),
                "notified_at": row.notified_at.isoformat() if row.notified_at else None,
                "first_action_at": (
                    row.first_action_at.isoformat() if row.first_action_at else None
                ),
            }
        )
    return out


def _sla_kpis(
    sla_hours: int = SLA_HOURS_DEFAULT,
    scope: str = "all_notified",
    now: datetime | None = None,
) -> dict:
    now = now or datetime.utcnow()
    sla_seconds = int(sla_hours * 3600)
    if scope not in {"all_notified", "assigned_only"}:
        raise ValueError("scope must be 'all_notified' or 'assigned_only'")

    base_states_q = db.session.query(
        VolunteerRequestState.request_id.label("req_id"),
        VolunteerRequestState.volunteer_id.label("vol_id"),
        VolunteerRequestState.notified_at.label("notified_at"),
        VolunteerRequestState.seen_at.label("seen_at"),
    ).filter(VolunteerRequestState.notified_at.isnot(None))
    if scope == "assigned_only":
        base_states_q = base_states_q.join(
            Request, Request.id == VolunteerRequestState.request_id
        ).filter(Request.assigned_volunteer_id == VolunteerRequestState.volunteer_id)
    base_states = base_states_q.subquery()

    seen_delta = func.strftime("%s", base_states.c.seen_at) - func.strftime(
        "%s", base_states.c.notified_at
    )
    avg_first_seen = (
        db.session.query(func.avg(seen_delta))
        .filter(base_states.c.seen_at.isnot(None))
        .filter(seen_delta >= 0)
        .scalar()
    )

    first_action_subq = (
        db.session.query(
            base_states.c.req_id.label("req_id"),
            base_states.c.vol_id.label("vol_id"),
            base_states.c.notified_at.label("notified_at"),
            func.min(RequestActivity.created_at).label("first_action_at"),
        )
        .join(
            RequestActivity,
            (RequestActivity.request_id == base_states.c.req_id)
            & (RequestActivity.volunteer_id == base_states.c.vol_id),
        )
        .filter(
            RequestActivity.action.in_(("volunteer_can_help", "volunteer_cant_help"))
        )
        .filter(RequestActivity.created_at >= base_states.c.notified_at)
        .group_by(
            base_states.c.req_id,
            base_states.c.vol_id,
            base_states.c.notified_at,
        )
        .subquery()
    )
    action_delta = func.strftime(
        "%s", first_action_subq.c.first_action_at
    ) - func.strftime("%s", first_action_subq.c.notified_at)
    avg_first_action = db.session.query(func.avg(action_delta)).scalar()

    under_count, total_count = (
        db.session.query(
            func.sum(case((action_delta <= sla_seconds, 1), else_=0)).label("under"),
            func.count().label("total"),
        ).first()
        or (0, 0)
    )
    under_count = int(under_count or 0)
    total_count = int(total_count or 0)
    sla_pct = round((under_count * 100.0 / total_count), 1) if total_count else 0.0
    p90_window_days = 7
    cutoff = now - timedelta(days=p90_window_days)
    seen_secs = [
        int(sec)
        for (sec,) in (
            db.session.query(seen_delta)
            .filter(base_states.c.seen_at.isnot(None))
            .filter(base_states.c.notified_at >= cutoff)
            .filter(seen_delta >= 0)
            .all()
        )
        if sec is not None
    ]
    action_secs = [
        int(sec)
        for (sec,) in (
            db.session.query(action_delta)
            .filter(first_action_subq.c.notified_at >= cutoff)
            .filter(first_action_subq.c.first_action_at >= cutoff)
            .filter(action_delta >= 0)
            .all()
        )
        if sec is not None
    ]
    outliers = _sla_outliers_action_7d(first_action_subq, now, limit=5)

    return {
        "avg_first_seen_seconds": (
            float(avg_first_seen) if avg_first_seen is not None else None
        ),
        "avg_first_action_seconds": (
            float(avg_first_action) if avg_first_action is not None else None
        ),
        "sla_under_12h_percent": sla_pct,
        "sla_hours": int(sla_hours),
        "sla_samples": total_count,
        "sla_scope": scope,
        "p90_first_seen_seconds_7d": _pctl(seen_secs, 0.9),
        "p90_first_action_seconds_7d": _pctl(action_secs, 0.9),
        "p90_window_days": p90_window_days,
        "sla_outliers_action_7d": outliers,
        "sla_outliers_window_days": 7,
        "sla_outliers_limit": 5,
    }


@admin_bp.get("/api/risk-kpis")
@admin_required
def admin_risk_kpis():
    admin_required_404()

    now = datetime.utcnow()
    stale_days = 8
    unassigned_days = 3
    window_days = 7
    not_seen_hours = 24

    stale_cutoff = now - timedelta(days=stale_days)
    unassigned_cutoff = now - timedelta(days=unassigned_days)
    window_cutoff = now - timedelta(days=window_days)
    has_vrs_notified_at = _table_has_column("volunteer_request_states", "notified_at")
    open_filter = or_(
        Request.status.is_(None), ~Request.status.in_(list(CLOSED_STATUSES))
    )

    stale_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at < stale_cutoff)
        .filter(open_filter)
        .scalar()
    )

    unassigned_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at < unassigned_cutoff)
        .filter(Request.assigned_volunteer_id.is_(None))
        .filter(open_filter)
        .scalar()
    )

    def count_notseen(hours: int) -> tuple[int, str]:
        cutoff = now - timedelta(hours=hours)
        if has_vrs_notified_at:
            cnt = (
                db.session.query(func.count(VolunteerRequestState.id))
                .join(Request, Request.id == VolunteerRequestState.request_id)
                .filter(VolunteerRequestState.notified_at.isnot(None))
                .filter(VolunteerRequestState.notified_at < cutoff)
                .filter(VolunteerRequestState.seen_at.is_(None))
                .filter(open_filter)
                .scalar()
            )
            source = "notified_at"
        else:
            cnt = (
                db.session.query(func.count(Notification.id))
                .join(Request, Request.id == Notification.request_id)
                .filter(Notification.type == "new_match")
                .filter(Notification.created_at < cutoff)
                .filter(open_filter)
                .scalar()
            )
            source = "notification_created_at_fallback"
        return int(cnt or 0), source

    notseen24, notified_source = count_notseen(24)
    notseen48, _ = count_notseen(48)
    notseen72, _ = count_notseen(72)
    notified_not_seen = notseen24

    can_help_7d = (
        db.session.query(func.count(VolunteerAction.id))
        .filter(VolunteerAction.action == "CAN_HELP")
        .filter(VolunteerAction.created_at >= window_cutoff)
        .scalar()
    )

    assigned_7d = (
        db.session.query(func.count(Request.id))
        .filter(Request.assigned_volunteer_id.isnot(None))
        .filter(Request.created_at >= window_cutoff)
        .scalar()
    )

    conversion = None
    if can_help_7d and can_help_7d > 0:
        conversion = round((assigned_7d / can_help_7d) * 100, 1)

    not_seen_by_request = {}
    try:
        if has_vrs_notified_at:
            cutoff = now - timedelta(hours=24)
            not_seen_rows = (
                db.session.query(
                    VolunteerRequestState.request_id, func.count(VolunteerRequestState.id)
                )
                .join(Request, Request.id == VolunteerRequestState.request_id)
                .filter(VolunteerRequestState.notified_at.isnot(None))
                .filter(VolunteerRequestState.notified_at < cutoff)
                .filter(VolunteerRequestState.seen_at.is_(None))
                .filter(open_filter)
                .group_by(VolunteerRequestState.request_id)
                .all()
            )
        else:
            cutoff = now - timedelta(hours=24)
            not_seen_rows = (
                db.session.query(Notification.request_id, func.count(Notification.id))
                .join(Request, Request.id == Notification.request_id)
                .filter(Notification.type == "new_match")
                .filter(Notification.created_at < cutoff)
                .filter(open_filter)
                .group_by(Notification.request_id)
                .all()
            )
        not_seen_by_request = {int(req_id): int(cnt) for req_id, cnt in not_seen_rows}
    except Exception:
        db.session.rollback()

    risky_candidates = (
        Request.query.filter(Request.deleted_at.is_(None))
        .filter(open_filter)
        .order_by(Request.created_at.asc())
        .limit(300)
        .all()
    )
    top_risky_scored = []
    for row in risky_candidates:
        created_at = getattr(row, "created_at", None)
        age_days = (
            max(0, int((now - created_at).total_seconds() // 86400))
            if created_at is not None
            else 0
        )
        is_unassigned = getattr(row, "assigned_volunteer_id", None) is None
        ns_count = int(not_seen_by_request.get(int(row.id), 0))
        score = 0
        if age_days >= stale_days:
            score += 3
        if is_unassigned and age_days >= unassigned_days:
            score += 4
        if ns_count > 0:
            score += 2 + min(3, ns_count)
        if score <= 0:
            continue
        top_risky_scored.append((score, age_days, ns_count, row))

    top_risky_scored.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3].id))
    top_risky = []
    for score, age_days, ns_count, row in top_risky_scored[:5]:
        top_risky.append(
            {
                "id": int(row.id),
                "title": getattr(row, "title", None) or f"Request #{row.id}",
                "days_open": int(age_days),
                "is_unassigned": bool(
                    getattr(row, "assigned_volunteer_id", None) is None
                ),
                "not_seen_count": int(ns_count),
                "risk_score": int(score),
                "details_url": url_for("admin.admin_request_details", req_id=row.id),
            }
        )

    payload = {
        "stale_days": stale_days,
        "unassigned_days": unassigned_days,
        "window_days": window_days,
        "not_seen_hours": not_seen_hours,
        "notified_source": notified_source,
        "stale_count": int(stale_count or 0),
        "unassigned_count": int(unassigned_count or 0),
        "notified_not_seen": int(notified_not_seen or 0),
        "notseen24": int(notseen24 or 0),
        "notseen48": int(notseen48 or 0),
        "notseen72": int(notseen72 or 0),
        "can_help_7d": int(can_help_7d or 0),
        "assigned_7d": int(assigned_7d or 0),
        "conversion_pct": conversion,
        "top_risky": top_risky,
        "generated_at": now.isoformat(timespec="seconds"),
    }
    requested_sla = request.args.get("sla", type=int)
    default_sla = int(current_app.config.get("SLA_HOURS_DEFAULT", SLA_HOURS_DEFAULT))
    sla_hours = requested_sla if requested_sla is not None else default_sla
    sla_hours = max(1, min(int(sla_hours), 168))
    payload.update(_sla_kpis(sla_hours=sla_hours, scope="all_notified", now=now))
    return jsonify(payload)


def _seconds_diff(end_col, start_col):
    """
    Portable-ish SQL expression for (end - start) in seconds.
    PostgreSQL: extract(epoch from end - start)
    SQLite/other: (julianday(end) - julianday(start)) * 86400
    """
    try:
        dialect = db.session.get_bind().dialect.name
    except Exception:
        dialect = ""
    if dialect == "postgresql":
        return func.extract("epoch", end_col - start_col)
    return (func.julianday(end_col) - func.julianday(start_col)) * 86400.0


@admin_bp.get("/api/ops-kpis")
@admin_required
def admin_ops_kpis():
    admin_required_404()

    days = max(1, min(int(request.args.get("days", 30) or 30), 365))
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    stale_since = now - timedelta(days=7)

    new_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at >= since)
        .scalar()
        or 0
    )

    resolved_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.completed_at.isnot(None))
        .filter(Request.completed_at >= since)
        .scalar()
        or 0
    )

    avg_to_owner_assign_sec = (
        db.session.query(func.avg(_seconds_diff(Request.owned_at, Request.created_at)))
        .filter(Request.owned_at.isnot(None))
        .scalar()
    )
    avg_owner_assign_hours = round(float(avg_to_owner_assign_sec or 0) / 3600.0, 2)

    avg_to_resolve_sec = (
        db.session.query(
            func.avg(_seconds_diff(Request.completed_at, Request.created_at))
        )
        .filter(Request.completed_at.isnot(None))
        .scalar()
    )
    avg_resolve_hours = round(float(avg_to_resolve_sec or 0) / 3600.0, 2)

    stale_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at < stale_since)
        .filter(Request.completed_at.is_(None))
        .scalar()
        or 0
    )

    by_category_rows = (
        db.session.query(Request.category, func.count(Request.id))
        .filter(Request.created_at >= since)
        .group_by(Request.category)
        .all()
    )
    by_category = [
        {"category": (category or "—"), "count": int(count)}
        for category, count in by_category_rows
    ]

    by_status_rows = (
        db.session.query(Request.status, func.count(Request.id))
        .filter(Request.completed_at.is_(None))
        .group_by(Request.status)
        .all()
    )
    by_status = [
        {"status": (status or "—"), "count": int(count)}
        for status, count in by_status_rows
    ]

    # --- SLA breach detection ---
    assign_deadline = now - timedelta(hours=ASSIGN_SLA_HOURS)
    resolve_deadline = now - timedelta(days=RESOLVE_SLA_DAYS)
    open_filter = or_(
        Request.status.is_(None), ~func.lower(Request.status).in_(CLOSED_STATUSES)
    )

    assign_breach_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at.isnot(None))
        .filter(Request.created_at < assign_deadline)
        .filter(Request.owned_at.is_(None))
        .filter(open_filter)
        .scalar()
        or 0
    )

    resolve_breach_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at.isnot(None))
        .filter(Request.created_at < resolve_deadline)
        .filter(Request.completed_at.is_(None))
        .filter(open_filter)
        .scalar()
        or 0
    )

    volunteer_assign_deadline = now - timedelta(hours=VOLUNTEER_ASSIGN_SLA_HOURS)
    volunteer_assign_breach_count = (
        db.session.query(func.count(Request.id))
        .filter(Request.created_at.isnot(None))
        .filter(Request.created_at < volunteer_assign_deadline)
        .filter(Request.assigned_volunteer_id.is_(None))
        .filter(open_filter)
        .scalar()
        or 0
    )

    # --- Health scoring (SLA-driven) ---
    if resolve_breach_count > 0:
        health_status = "critique"
    elif assign_breach_count > 0:
        health_status = "sous_tension"
    else:
        health_status = "stable"

    return jsonify(
        {
            "window_days": days,
            "new_requests": int(new_count),
            "resolved_requests": int(resolved_count),
            "avg_owner_assign_hours": avg_owner_assign_hours,
            "avg_resolve_hours": avg_resolve_hours,
            "stale_over_7d": int(stale_count),
            "by_category": by_category,
            "by_status_open": by_status,
            "definition": {
                "assignment": "owner assignment (owner_id + owned_at)",
                "resolution": "completed_at not null",
            },
            "sla": {
                "assign_sla_hours": ASSIGN_SLA_HOURS,
                "resolve_sla_days": RESOLVE_SLA_DAYS,
                "assign_breach_count": int(assign_breach_count),
                "resolve_breach_count": int(resolve_breach_count),
            },
            "health": {
                "status": health_status,
            },
            "volunteer_sla": {
                "volunteer_assign_sla_hours": VOLUNTEER_ASSIGN_SLA_HOURS,
                "volunteer_assign_breach_count": int(volunteer_assign_breach_count),
            },
        }
    )


@admin_bp.route("/")
@admin_required
def admin_dashboard():
    admin_required_404()
    """Админ панел"""

    import logging

    logging.warning(
        f"[DEBUG] admin_dashboard: is_authenticated={getattr(current_user, 'is_authenticated', None)}, is_admin={getattr(current_user, 'is_admin', None)}, id={getattr(current_user, 'id', None)}, username={getattr(current_user, 'username', None)}"
    )
    if not current_user.is_admin:
        flash("Нямате достъп до админ панела.", "error")
        return redirect(url_for("main.dashboard"))

    requests = Request.query.all()
    logs = RequestLog.query.all()
    volunteers = Volunteer.query.all()
    logs_dict = {}
    for log in logs:
        if log.request_id not in logs_dict:
            logs_dict[log.request_id] = []
        logs_dict[log.request_id].append(log)

    # Convert to JSON serializable format
    requests_dict = []
    for r in requests:
        # Fallback location using location_text -> city/region
        loc = (
            getattr(r, "location_text", None)
            or ", ".join(
                [
                    val
                    for val in (getattr(r, "city", None), getattr(r, "region", None))
                    if val
                ]
            )
            or ""
        )
        requests_dict.append(
            {
                "id": r.id,
                "name": r.name,
                "phone": r.phone,
                "email": r.email,
                "location": loc,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                # Map urgency to priority if urgency field is missing
                "urgency": getattr(r, "urgency", None) or getattr(r, "priority", None),
            }
        )

    volunteers_dict = [
        {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "location": v.location,
            "skills": v.skills,
        }
        for v in volunteers
    ]

    # Defensive stats: ensure templates always receive a `stats` mapping
    try:
        total_requests = len(requests) if requests is not None else 0
    except Exception:
        total_requests = 0
    try:
        pending_requests = sum(
            1
            for r in requests
            if getattr(r, "status", None) not in ("completed", "done", None)
        )
    except Exception:
        pending_requests = 0
    try:
        total_volunteers = len(volunteers) if volunteers is not None else 0
    except Exception:
        total_volunteers = 0

    stats = {
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "total_volunteers": total_volunteers,
    }

    try:
        now = utc_now()
        week_ago = now - timedelta(days=7)

        total_requests_cnt = db.session.query(func.count(Request.id)).scalar() or 0

        open_requests_cnt = (
            db.session.query(func.count(Request.id))
            .filter(Request.status.notin_(["done", "rejected"]))
            .scalar()
            or 0
        )

        closed_requests_cnt = (
            db.session.query(func.count(Request.id))
            .filter(Request.status.in_(["done", "rejected"]))
            .scalar()
            or 0
        )

        closed_last_7d_cnt = (
            db.session.query(func.count(Request.id))
            .filter(Request.completed_at.isnot(None), Request.completed_at >= week_ago)
            .scalar()
            or 0
        )

        avg_resolution_hours = (
            db.session.query(
                func.avg(
                    func.julianday(Request.completed_at)
                    - func.julianday(Request.created_at)
                )
                * 24.0
            )
            .filter(Request.completed_at.isnot(None), Request.created_at.isnot(None))
            .scalar()
        )
        avg_resolution_hours = (
            float(avg_resolution_hours) if avg_resolution_hours is not None else None
        )

        unassigned_over_2d_cnt = (
            db.session.query(func.count(Request.id))
            .filter(
                Request.owner_id.is_(None),
                Request.status.notin_(["done", "rejected"]),
                Request.created_at <= (now - timedelta(days=2)),
            )
            .scalar()
            or 0
        )

        high_open_count = (
            db.session.query(func.count(Request.id))
            .filter(Request.status.notin_(["done", "rejected"]))
            .filter(Request.priority == "high")
            .scalar()
            or 0
        )

        stale_open_count = (
            db.session.query(func.count(Request.id))
            .filter(Request.status.notin_(["done", "rejected"]))
            .filter(Request.created_at <= (now - timedelta(days=7)))
            .scalar()
            or 0
        )

        # --- Requests per day (last 14 days) ---
        since_dt = now - timedelta(days=14)
        rows = (
            db.session.query(func.date(Request.created_at), func.count(Request.id))
            .filter(Request.created_at.isnot(None))
            .filter(Request.created_at >= since_dt)
            .group_by(func.date(Request.created_at))
            .order_by(func.date(Request.created_at))
            .all()
        )
        impact_dates = [str(r[0]) for r in rows]
        impact_counts = [int(r[1]) for r in rows]

        # --- Requests by category ---
        cat_rows = (
            db.session.query(Request.category, func.count(Request.id))
            .group_by(Request.category)
            .order_by(func.count(Request.id).desc())
            .all()
        )
        impact_cat_labels = [r[0] or "unknown" for r in cat_rows]
        impact_cat_counts = [int(r[1]) for r in cat_rows]

        impact = {
            "total": total_requests_cnt,
            "open": open_requests_cnt,
            "closed": closed_requests_cnt,
            "closed_last_7d": closed_last_7d_cnt,
            "avg_resolution_hours": avg_resolution_hours,
            "unassigned_over_2d": unassigned_over_2d_cnt,
            "open_requests": int(open_requests_cnt or 0),
            "unassigned_48h": int(unassigned_over_2d_cnt or 0),
            "requests_dates": impact_dates,
            "requests_counts": impact_counts,
            "cat_labels": impact_cat_labels,
            "cat_counts": impact_cat_counts,
            "high_open": int(high_open_count or 0),
            "stale_open": int(stale_open_count or 0),
        }
    except Exception:
        impact = {
            "total": 0,
            "open": 0,
            "closed": 0,
            "closed_last_7d": 0,
            "avg_resolution_hours": None,
            "unassigned_over_2d": 0,
            "open_requests": 0,
            "unassigned_48h": 0,
            "requests_dates": [],
            "requests_counts": [],
            "cat_labels": [],
            "cat_counts": [],
            "high_open": 0,
            "stale_open": 0,
        }

    # Log the final template context summary for diagnostics during tests
    try:
        import logging as _logging

        _log = _logging.getLogger(__name__)
        _log.info(
            "admin_dashboard rendering: stats=%s, requests_items=%s, volunteers=%s",
            stats,
            total_requests,
            total_volunteers,
        )
    except Exception:
        pass

    return render_template(
        "admin_dashboard.html",
        requests={"items": requests},
        logs_dict=logs_dict,
        requests_json=requests_dict,
        volunteers=volunteers,
        volunteers_json=volunteers_dict,
        stats=stats,
        impact=impact,
        STATUS_LABELS=STATUS_LABELS,
    )


@admin_bp.route("/volunteers", methods=["GET"])
@admin_required
def admin_volunteers():
    admin_required_404()
    """Управление на доброволци"""

    import logging

    logging.warning(
        f"[DEBUG] admin_volunteers: is_authenticated={getattr(current_user, 'is_authenticated', None)}, is_admin={getattr(current_user, 'is_admin', None)}, id={getattr(current_user, 'id', None)}, username={getattr(current_user, 'username', None)}"
    )
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    volunteers = Volunteer.query.all()
    return render_template("admin_volunteers.html", volunteers=volunteers)


@admin_bp.route("/admin_volunteers", methods=["GET"])
@admin_required
def admin_volunteers_compat():
    admin_required_404()
    return redirect(url_for("admin.admin_volunteers"), code=302)


@admin_bp.route("/admin_volunteers/add", methods=["GET", "POST"])
@admin_required
def add_volunteer():
    admin_required_404()
    """Добавяне на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        volunteer = Volunteer(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            location=request.form["location"],
            skills=request.form.get("skills", ""),
        )
        db.session.add(volunteer)
        db.session.commit()
        flash("Доброволецът е добавен успешно!", "success")
        return redirect(url_for("admin.admin_volunteers"))

    return render_template("add_volunteer.html")


@admin_bp.route("/delete_volunteer/<int:id>", methods=["POST"])
@admin_required
def delete_volunteer(id):
    admin_required_404()
    """Изтриване на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    from flask import abort

    volunteer = db.session.get(Volunteer, id)
    if not volunteer:
        abort(404)
    db.session.delete(volunteer)
    db.session.commit()
    flash("Доброволецът е изтрит успешно!", "success")
    return redirect(url_for("admin.admin_volunteers"))


@admin_bp.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_volunteer(id):
    admin_required_404()
    """Редактиране на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    from flask import abort

    volunteer = db.session.get(Volunteer, id)
    if not volunteer:
        abort(404)

    import logging

    if request.method == "POST":
        logging.warning(f"[DEBUG] POST data: {request.form}")
        volunteer.name = request.form["name"]
        volunteer.email = request.form["email"]
        volunteer.phone = request.form["phone"]
        volunteer.location = request.form["location"]
        volunteer.skills = request.form.get("skills", "")
        logging.warning(
            f"[DEBUG] Before commit: name={volunteer.name}, email={volunteer.email}, phone={volunteer.phone}, location={volunteer.location}, skills={volunteer.skills}"
        )
        db.session.commit()
        logging.warning(
            f"[DEBUG] After commit: id={volunteer.id}, email={volunteer.email}"
        )
        flash("Промените са запазени!", "success")
        return redirect(url_for("admin.admin_volunteers"))

    return render_template("edit_volunteer.html", volunteer=volunteer)


@admin_bp.route("/export_volunteers")
@admin_required
def export_volunteers():
    admin_required_404()
    """Експорт на доброволци като CSV"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    import csv
    from io import StringIO

    from flask import Response

    volunteers = Volunteer.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Име", "Имейл", "Телефон", "Град/регион", "Умения"])
    for v in volunteers:
        cw.writerow([v.name, v.email, v.phone, v.location, v.skills])

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=volunteers.csv"},
    )


@admin_bp.route("/update_status/<int:req_id>", methods=["POST"])
@admin_required
def update_status(req_id):
    admin_required_404()
    """Обновяване статуса на заявка"""
    from flask import current_app

    if not current_app.config.get("TESTING", False):
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Unauthorized"}), 403

    req = db.session.get(Request, req_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    if not can_edit_request(req, current_user):
        abort(403)

    new_status = (request.form.get("status") or "").strip()
    old_raw_status = req.status
    old_status = normalize_request_status(old_raw_status)
    new_status = normalize_request_status(new_status)

    if new_status not in REQUEST_STATUS_ALLOWED:
        current_app.logger.warning(
            "ADMIN update_status blocked invalid new_status=%r for request_id=%s",
            new_status,
            req_id,
        )
        flash("Invalid status.", "warning")
        return redirect(url_for("admin.admin_request_details", req_id=req_id))

    # Guard: no-op changes shouldn't log noise
    if not new_status or new_status == old_status:
        if request.is_json or (
            request.accept_mimetypes
            and request.accept_mimetypes.best == "application/json"
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "status": old_status,
                        "message": "No status change.",
                    }
                ),
                200,
            )
        flash("No status change.", "info")
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    # ✅ SUCCESS PATH (was accidentally placed under the alias handler)
    req.status = new_status
    closing_statuses = {"done", "cancelled"}
    if new_status in closing_statuses:
        req.completed_at = utc_now()
    else:
        req.completed_at = None
    # Activity + legacy request log (single commit)
    log_request_activity(
        req,
        "status_change",
        old=old_status,
        new=new_status,
        actor_admin_id=getattr(current_user, "id", None),
    )
    _audit_request(
        req.id,
        action="status_change",
        message="Status updated",
        old=old_status,
        new=new_status,
    )
    # metrics
    metric = db.session.query(RequestMetric).filter_by(request_id=req.id).first()
    if metric is None:
        metric = RequestMetric(request_id=req.id)
        db.session.add(metric)
    if new_status == "done" and metric.time_to_complete is None and req.created_at:
        try:
            metric.time_to_complete = int((utc_now() - req.created_at).total_seconds())
        except Exception:
            pass

    # --- Bulletproof policy sync: VolunteerInterest follows Request.status + owner_id ---
    from backend.helpchain_backend.src.models.volunteer_interest import (
        VolunteerInterest,
    )

    if new_status == "in_progress":
        if not getattr(req, "owner_id", None):
            current_app.logger.warning(
                "Interest sync skipped: request_id=%s set to in_progress without owner_id",
                req.id,
            )
        else:
            q = VolunteerInterest.query.filter_by(request_id=req.id)

            # Ensure owner's latest interest exists and is approved
            owner_latest = (
                q.filter_by(volunteer_id=req.owner_id)
                .order_by(VolunteerInterest.id.desc())
                .first()
            )
            if owner_latest is None:
                owner_latest = VolunteerInterest(
                    request_id=req.id,
                    volunteer_id=req.owner_id,
                    status="approved",
                )
                db.session.add(owner_latest)
                current_app.logger.info(
                    "Interest sync: created approved owner interest (request_id=%s, volunteer_id=%s)",
                    req.id,
                    req.owner_id,
                )
            elif owner_latest.status != "approved":
                owner_latest.status = "approved"
                db.session.add(owner_latest)
                current_app.logger.info(
                    "Interest sync: set owner interest to approved (request_id=%s, volunteer_id=%s)",
                    req.id,
                    req.owner_id,
                )

            # Reject other pending interests
            pending_others = (
                q.filter(VolunteerInterest.status == "pending")
                .filter(VolunteerInterest.volunteer_id != req.owner_id)
                .all()
            )
            for vi_row in pending_others:
                vi_row.status = "rejected"
                db.session.add(vi_row)

            if pending_others:
                current_app.logger.info(
                    "Interest sync: rejected %s pending interests (request_id=%s, owner_id=%s)",
                    len(pending_others),
                    req.id,
                    req.owner_id,
                )

    elif new_status in {"done", "cancelled"}:
        q = VolunteerInterest.query.filter_by(request_id=req.id)
        pending_all = q.filter(VolunteerInterest.status == "pending").all()
        for vi_row in pending_all:
            vi_row.status = "rejected"
            db.session.add(vi_row)

        if pending_all:
            current_app.logger.info(
                "Interest sync: rejected %s pending interests on close (request_id=%s, new_status=%s)",
                len(pending_all),
                req.id,
                new_status,
            )

    db.session.commit()

    # Изпращане на email при промяна на статус (graceful fallback)
    try:
        from backend.mail_service import send_notification_email

        subject = f"Статусът на вашата заявка #{req.id} е променен на {new_status}"
        recipient = getattr(req, "email", None)
        recipient_name = getattr(req, "name", "Потребител")
        content = f"Статусът на вашата заявка е променен на <b>{new_status}</b>.\n\nОписание: {req.description or ''}"
        context = {
            "subject": subject,
            "recipient_name": recipient_name,
            "content": content,
            "request_id": req.id,
            "new_status": new_status,
            "description": req.description,
            "updated_at": req.updated_at,
        }
        if recipient:
            send_notification_email(recipient, subject, "email_template.html", context)
    except ModuleNotFoundError:
        import logging

        logging.info(
            "[EMAIL] mail_service not configured; email sending skipped (dev mode)"
        )
    except Exception as e:
        import logging

        logging.warning(
            f"[EMAIL] Неуспешно изпращане на email при промяна на статус: {e}"
        )

    # Ако е JSON/AJAX – връщаме JSON; иначе redirect за формата
    if request.is_json or (
        request.accept_mimetypes and request.accept_mimetypes.best == "application/json"
    ):
        return jsonify({"success": True, "status": new_status or req.status})
    flash("Статусът е обновен.", "success")
    return redirect(url_for("admin.admin_request_details", req_id=req_id))


@admin_bp.post("/requests/<int:req_id>/status")
@admin_required
def admin_request_set_status(req_id: int):
    # Alias: keep old canonical handler, just expose the “resource” URL too.
    return update_status(req_id)


@admin_bp.post("/requests/<int:req_id>/archive", endpoint="admin_request_archive")
@login_required
def admin_request_archive(req_id: int):
    """One-click archive/close action used by the details view button."""
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)

    old_status = normalize_request_status(getattr(req, "status", None))
    req.status = "cancelled"
    req.completed_at = utc_now()
    req.is_archived = True
    if getattr(req, "archived_at", None) is None:
        req.archived_at = utc_now()

    log_request_activity(
        req,
        "status_change",
        old=old_status,
        new="cancelled",
        actor_admin_id=getattr(current_user, "id", None),
    )
    db.session.commit()
    flash("Request archived and closed.", "success")
    return redirect(url_for("admin.admin_request_details", req_id=req.id))


from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, tuple_

from ..models import Request, RequestActivity, db

ALLOWED_STATUSES = {"pending", "approved", "in_progress", "done", "rejected"}

STATUS_LABELS_BG = {
    "pending": "Чакащи",
    "approved": "Одобрени",
    "in_progress": "В процес",
    "done": "Приключени",
    "rejected": "Отхвърлени",
}

# Canonical EN msgids for status labels - passed to templates for localization
STATUS_LABELS = {
    "pending": "Pending",
    "approved": "Approved",
    "in_progress": "In progress",
    "done": "Completed",
    "rejected": "Rejected",
}


@admin_bp.get("/risk")
@admin_required
def admin_risk_panel():
    admin_required_404()
    return render_template("admin/risk_panel.html")


@admin_bp.get("/sla")
@admin_required
def admin_sla_breakdown():
    admin_required_404()

    breach_type = (request.args.get("type") or "owner_assign").strip().lower()
    if breach_type not in {"all", "resolve", "owner_assign", "volunteer_assign"}:
        breach_type = "owner_assign"
    sort = (request.args.get("sort") or "overdue").strip().lower()
    days = max(1, min(int(request.args.get("days", 30) or 30), 365))
    limit = max(1, min(int(request.args.get("limit", 200) or 200), 1000))

    now = datetime.utcnow()
    window_start = now - timedelta(days=days)

    open_filter = or_(
        Request.status.is_(None), ~func.lower(Request.status).in_(CLOSED_STATUSES)
    )

    owner_assign_sla_hours = int(ASSIGN_SLA_HOURS)
    resolve_sla_hours = int(RESOLVE_SLA_DAYS * 24)
    volunteer_assign_sla_hours = int(VOLUNTEER_ASSIGN_SLA_HOURS)

    q = (
        db.session.query(Request)
        .filter(Request.created_at.isnot(None))
        .filter(Request.created_at >= window_start)
        .filter(open_filter)
    )

    if breach_type == "resolve":
        breach_label = "SLA résolution"
    elif breach_type == "owner_assign":
        breach_label = "SLA assignation owner"
    elif breach_type == "volunteer_assign":
        breach_label = "Affectation bénévole"
    else:
        breach_label = "Toutes violations"

    requests = q.all()

    rows: list[dict] = []
    resolve_count = 0
    owner_assign_count = 0
    volunteer_assign_count = 0

    for req in requests:
        created_at = _to_utc_naive(getattr(req, "created_at", None))
        if not created_at:
            continue
        age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)

        resolve_overdue = None
        owner_assign_overdue = None
        volunteer_assign_overdue = None

        if req.completed_at is None and age_hours > resolve_sla_hours:
            resolve_overdue = age_hours - resolve_sla_hours
            resolve_count += 1

        if req.owner_id is None and age_hours > owner_assign_sla_hours:
            owner_assign_overdue = age_hours - owner_assign_sla_hours
            owner_assign_count += 1

        if req.assigned_volunteer_id is None and age_hours > volunteer_assign_sla_hours:
            volunteer_assign_overdue = age_hours - volunteer_assign_sla_hours
            volunteer_assign_count += 1

        candidates = []
        if resolve_overdue is not None:
            candidates.append(("resolve", resolve_overdue))
        if owner_assign_overdue is not None:
            candidates.append(("owner_assign", owner_assign_overdue))
        if volunteer_assign_overdue is not None:
            candidates.append(("volunteer_assign", volunteer_assign_overdue))

        if not candidates:
            continue

        if breach_type == "all":
            row_breach_type, overdue_hours = max(candidates, key=lambda x: x[1])
        else:
            picked = {k: v for k, v in candidates}.get(breach_type)
            if picked is None:
                continue
            row_breach_type, overdue_hours = breach_type, picked

        rows.append(
            {
                "id": req.id,
                "title": req.title,
                "category": req.category,
                "status": req.status,
                "created_at": req.created_at,
                "owner_id": req.owner_id,
                "assigned_volunteer_id": req.assigned_volunteer_id,
                "overdue_hours": round(float(overdue_hours), 1),
                "breach_type": row_breach_type,
            }
        )

    def _created_ts(row: dict) -> float:
        dt = _to_utc_naive(row.get("created_at"))
        return dt.timestamp() if dt else 0.0

    if sort == "created":
        rows.sort(key=_created_ts)
    else:
        rows.sort(key=lambda r: (-(float(r.get("overdue_hours") or 0.0)), _created_ts(r)))
    rows = rows[:limit]

    return render_template(
        "admin/sla.html",
        breach_label=breach_label,
        breach_type=breach_type,
        days=days,
        sort=sort,
        limit=limit,
        resolve_count=int(resolve_count),
        owner_assign_count=int(owner_assign_count),
        volunteer_assign_count=int(volunteer_assign_count),
        rows=rows,
    )


@admin_bp.get("/requests")
@login_required
def admin_requests():
    admin_required_404()
    STATUS_LABELS_BG = {
        "new": "Нови",
        "pending": "Чакащи",
        "approved": "Одобрени",
        "in_progress": "В процес",
        "done": "Приключени",
        "rejected": "Отхвърлени",
    }

    show_deleted = (request.args.get("deleted") or "").strip() == "1"
    query = Request.query
    query, status, q, risk = build_requests_query(query, request.args)
    requests = query.all()
    now_aware = utc_now()
    now_naive = datetime.utcnow()
    SLA_WARN_NO_OWNER_DAYS = 2
    SLA_STALE_DAYS = 7
    risk_notseen_tier_hours = _notseen_hours_from_risk(risk)

    # Volunteer signals counts per request
    action_counts = {}
    last_signal_by_req = {}
    engagement_by_request = {}
    nudge_ui = {}
    if requests:
        req_ids = [r.id for r in requests]
        rows = (
            db.session.query(
                VolunteerAction.request_id,
                VolunteerAction.action,
                func.count(VolunteerAction.id),
            )
            .filter(VolunteerAction.request_id.in_(req_ids))
            .group_by(VolunteerAction.request_id, VolunteerAction.action)
            .all()
        )
        for rid, act, cnt in rows:
            action_counts.setdefault(rid, {}).update({act: cnt})

        # --- Last volunteer signal per request (page only) ---
        # One extra query for this page, avoids N+1 and makes "can't help" visible.
        last_rows = (
            VolunteerAction.query.filter(VolunteerAction.request_id.in_(req_ids))
            .order_by(
                VolunteerAction.request_id.asc(),
                VolunteerAction.updated_at.desc(),
                VolunteerAction.created_at.desc(),
            )
            .all()
        )
        # pick first (newest) per request_id (because ordered desc by updated_at/created_at)
        for a in last_rows:
            if a.request_id not in last_signal_by_req:
                last_signal_by_req[a.request_id] = a

        assigned_volunteer_ids = sorted(
            {
                int(r.assigned_volunteer_id)
                for r in requests
                if getattr(r, "assigned_volunteer_id", None)
            }
        )
        engagement_by_volunteer = {}
        for volunteer_id in assigned_volunteer_ids:
            try:
                engagement_by_volunteer[volunteer_id] = get_volunteer_engagement_score(
                    volunteer_id, now=now_naive
                )
            except Exception:
                db.session.rollback()
                engagement_by_volunteer[volunteer_id] = {
                    "volunteer_id": int(volunteer_id),
                    "score": 0,
                    "label": "At risk",
                    "seen_within_24h": 0,
                    "not_seen_72h": 0,
                    "can_help": 0,
                    "cant_help": 0,
                }
        engagement_by_request = {
            r.id: engagement_by_volunteer.get(getattr(r, "assigned_volunteer_id", None))
            for r in requests
        }

        # Pair-safe nudge cooldown status for queue rows (single query; no N+1).
        def _to_utc_naive(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt
            return dt.astimezone(timezone.utc).replace(tzinfo=None)

        now = datetime.utcnow()
        cooldown = timedelta(hours=NUDGE_COOLDOWN_HOURS)
        pairs = {
            (r.id, int(r.assigned_volunteer_id))
            for r in requests
            if getattr(r, "id", None) and getattr(r, "assigned_volunteer_id", None)
        }
        nudge_by_pair: dict[tuple[int, int], datetime] = {}

        if pairs:
            try:
                nudge_rows = (
                    db.session.query(
                        Notification.request_id,
                        Notification.volunteer_id,
                        Notification.created_at,
                    )
                    .filter(Notification.type == "admin_nudge")
                    .filter(
                        tuple_(
                            Notification.request_id, Notification.volunteer_id
                        ).in_(pairs)
                    )
                    .all()
                )
            except Exception:
                req_ids = {req_id for req_id, _ in pairs}
                nudge_rows = (
                    db.session.query(
                        Notification.request_id,
                        Notification.volunteer_id,
                        Notification.created_at,
                    )
                    .filter(Notification.type == "admin_nudge")
                    .filter(Notification.request_id.in_(req_ids))
                    .all()
                )

            for req_id, vol_id, created_at in nudge_rows:
                if (req_id, vol_id) not in pairs:
                    continue
                created_naive = _to_utc_naive(created_at)
                if not created_naive:
                    continue
                key = (int(req_id), int(vol_id))
                prev = nudge_by_pair.get(key)
                if prev is None or created_naive > prev:
                    nudge_by_pair[key] = created_naive

        for r in requests:
            rid = getattr(r, "id", None)
            vid = getattr(r, "assigned_volunteer_id", None)
            if not rid:
                continue
            if not vid:
                nudge_ui[rid] = {"disabled": True, "title": "No assigned volunteer"}
                continue

            created_at = nudge_by_pair.get((rid, int(vid)))
            if not created_at:
                nudge_ui[rid] = {
                    "disabled": False,
                    "title": "Send reminder to assigned volunteer",
                }
                continue

            next_at = created_at + cooldown
            if next_at > now:
                remaining = next_at - now
                mins = int(remaining.total_seconds() // 60)
                hrs = mins // 60
                mm = mins % 60
                if hrs > 0:
                    tip = f"Nudge available in {hrs}h {mm}m"
                else:
                    tip = f"Nudge available in {mm}m"
                nudge_ui[rid] = {"disabled": True, "title": tip}
            else:
                nudge_ui[rid] = {
                    "disabled": False,
                    "title": "Send reminder to assigned volunteer",
                }

    return render_template(
        "admin/requests.html",
        STATUS_LABELS_BG=STATUS_LABELS_BG,
        STATUS_LABELS=STATUS_LABELS,
        requests=requests,
        status=status,
        q=q,
        risk=risk,
        show_deleted=show_deleted,
        now_aware=now_aware,
        now_naive=now_naive,
        SLA_WARN_NO_OWNER_DAYS=SLA_WARN_NO_OWNER_DAYS,
        SLA_STALE_DAYS=SLA_STALE_DAYS,
        volunteer_action_counts=action_counts,
        last_signal_by_req=last_signal_by_req,
        engagement_by_request=engagement_by_request,
        nudge_ui=nudge_ui,
        risk_notseen_tier_hours=risk_notseen_tier_hours,
    )


def apply_risk_filter(base_query, risk: str, now: datetime):
    closed_statuses = {"done", "cancelled", "rejected"}
    open_filter = or_(
        Request.status.is_(None), ~func.lower(Request.status).in_(closed_statuses)
    )
    notseen_hours = _notseen_hours_from_risk(risk)
    if (
        risk
        not in {
            "stale",
            "unassigned",
            "assigned_recent",
            "volunteer_stale",
            "sla_resolve_breach",
            "sla_assign_breach",
        }
        and notseen_hours is None
    ):
        return base_query

    if risk == "stale":
        base_query = base_query.filter(Request.created_at < (now - timedelta(days=8)))
        base_query = base_query.filter(open_filter)
    elif risk == "unassigned":
        base_query = base_query.filter(
            Request.created_at < (now - timedelta(days=3)),
            Request.assigned_volunteer_id.is_(None),
        )
        base_query = base_query.filter(open_filter)
    elif risk == "assigned_recent":
        base_query = base_query.filter(
            Request.created_at >= (now - timedelta(days=7)),
            Request.assigned_volunteer_id.isnot(None),
        )
    elif risk == "volunteer_stale":
        base_query = base_query.filter(
            Request.created_at < (now - timedelta(hours=VOLUNTEER_ASSIGN_SLA_HOURS)),
            Request.assigned_volunteer_id.is_(None),
        )
        base_query = base_query.filter(open_filter)
    elif risk == "sla_resolve_breach":
        base_query = base_query.filter(
            Request.created_at < (now - timedelta(days=RESOLVE_SLA_DAYS)),
            Request.completed_at.is_(None),
        )
        base_query = base_query.filter(open_filter)
    elif risk == "sla_assign_breach":
        base_query = base_query.filter(
            Request.created_at < (now - timedelta(hours=ASSIGN_SLA_HOURS)),
            Request.owned_at.is_(None),
        )
        base_query = base_query.filter(open_filter)
    elif notseen_hours is not None:
        notseen_subq, _source = _build_notseen_subquery(now, hours=notseen_hours)
        base_query = base_query.filter(Request.id.in_(notseen_subq))
        base_query = base_query.filter(open_filter)
    return base_query


def build_requests_query(base_query, request_args):
    status = (request_args.get("status") or "").strip()
    q = (request_args.get("q") or "").strip()
    category = (request_args.get("category") or "").strip()
    risk = (request_args.get("risk") or "").strip().lower()
    show_deleted = (request_args.get("deleted") or "").strip() == "1"
    now = datetime.utcnow()

    if show_deleted:
        base_query = base_query.filter(Request.deleted_at.isnot(None))
    else:
        base_query = base_query.filter(Request.deleted_at.is_(None))

    if status:
        internal = "pending" if status == "new" else status
        base_query = base_query.filter(Request.status == internal)
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            or_(
                Request.title.ilike(like),
                Request.name.ilike(like),
                Request.email.ilike(like),
                Request.phone.ilike(like),
                Request.description.ilike(like),
            )
        )
    if category:
        base_query = base_query.filter(func.lower(Request.category) == category.lower())

    base_query = apply_risk_filter(base_query, risk, now)

    base_query = base_query.order_by(Request.id.desc())
    return base_query, status, q, risk


@admin_bp.get("/requests/export.csv")
@admin_required
def admin_requests_export_csv():
    admin_required_404()
    query, _status, _q, _risk = build_requests_query(Request.query, request.args)
    rows = query.limit(5000).all()
    log_activity(
        entity_type="export",
        entity_id=0,
        action="requests_export",
        message="Requests export",
        meta={"format": "csv", "anonymized": False},
        persist=True,
    )

    out = StringIO()
    # Excel-friendly CSV for EU locales: UTF-8 BOM + semicolon delimiter.
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        [
            "id",
            "created_at",
            "status",
            "priority",
            "category",
            "title",
            "name",
            "email",
            "phone",
            "owner_id",
            "owned_at",
            "completed_at",
        ]
    )

    for r in rows:
        writer.writerow(
            [
                r.id,
                getattr(r, "created_at", "") or "",
                getattr(r, "status", "") or "",
                getattr(r, "priority", "") or "",
                getattr(r, "category", "") or "",
                getattr(r, "title", "") or "",
                getattr(r, "name", "") or "",
                getattr(r, "email", "") or "",
                getattr(r, "phone", "") or "",
                getattr(r, "owner_id", "") or "",
                getattr(r, "owned_at", "") or "",
                getattr(r, "completed_at", "") or "",
            ]
        )

    filename = f"helpchain_requests_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_bp.get("/requests/export.xlsx")
@admin_required
def admin_requests_export_xlsx():
    admin_required_404()
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except Exception:
        return Response("openpyxl is not installed", status=500)

    query, _status, _q, _risk = build_requests_query(Request.query, request.args)
    rows = query.limit(5000).all()
    log_activity(
        entity_type="export",
        entity_id=0,
        action="requests_export",
        message="Requests export",
        meta={"format": "xlsx", "anonymized": False},
        persist=True,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Requests"
    headers = [
        "id",
        "created_at",
        "status",
        "priority",
        "category",
        "title",
        "name",
        "email",
        "phone",
        "owner_id",
        "owned_at",
        "completed_at",
    ]
    ws.append(headers)

    for r in rows:
        ws.append(
            [
                r.id,
                getattr(r, "created_at", None),
                getattr(r, "status", None),
                getattr(r, "priority", None),
                getattr(r, "category", None),
                getattr(r, "title", None),
                getattr(r, "name", None),
                getattr(r, "email", None),
                getattr(r, "phone", None),
                getattr(r, "owner_id", None),
                getattr(r, "owned_at", None),
                getattr(r, "completed_at", None),
            ]
        )

    # Keep phone values as text to avoid Excel scientific notation.
    phone_col = headers.index("phone") + 1
    for row_idx in range(2, ws.max_row + 1):
        cell = ws.cell(row=row_idx, column=phone_col)
        if cell.value is not None:
            cell.value = str(cell.value)
        cell.number_format = "@"

    # Auto-fit column widths for readable exports.
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in col_cells:
            val = "" if cell.value is None else str(cell.value)
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(10, max_len + 2), 60
        )

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"helpchain_requests_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.get("/requests/export_anonymized.csv")
@admin_required
def admin_requests_export_csv_anonymized():
    admin_required_404()
    query, _status, _q, _risk = build_requests_query(Request.query, request.args)
    rows = query.limit(5000).all()
    log_activity(
        entity_type="export",
        entity_id=0,
        action="requests_export",
        message="Requests export (anonymized)",
        meta={"format": "csv", "anonymized": True},
        persist=True,
    )

    out = StringIO()
    # Excel-friendly CSV for EU locales: UTF-8 BOM + semicolon delimiter.
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        [
            "id",
            "created_at",
            "status",
            "priority",
            "category",
            "owner_id",
            "owned_at",
            "completed_at",
        ]
    )

    for r in rows:
        writer.writerow(
            [
                r.id,
                getattr(r, "created_at", "") or "",
                getattr(r, "status", "") or "",
                getattr(r, "priority", "") or "",
                getattr(r, "category", "") or "",
                getattr(r, "owner_id", "") or "",
                getattr(r, "owned_at", "") or "",
                getattr(r, "completed_at", "") or "",
            ]
        )

    filename = (
        f"helpchain_requests_ANON_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_bp.get("/requests/export_anonymized.xlsx")
@admin_required
def admin_requests_export_xlsx_anonymized():
    admin_required_404()
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except Exception:
        return Response("openpyxl is not installed", status=500)

    query, _status, _q, _risk = build_requests_query(Request.query, request.args)
    rows = query.limit(5000).all()
    log_activity(
        entity_type="export",
        entity_id=0,
        action="requests_export",
        message="Requests export (anonymized)",
        meta={"format": "xlsx", "anonymized": True},
        persist=True,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Requests (Anon)"
    headers = [
        "id",
        "created_at",
        "status",
        "priority",
        "category",
        "owner_id",
        "owned_at",
        "completed_at",
    ]
    ws.append(headers)

    for r in rows:
        ws.append(
            [
                r.id,
                getattr(r, "created_at", None),
                getattr(r, "status", None),
                getattr(r, "priority", None),
                getattr(r, "category", None),
                getattr(r, "owner_id", None),
                getattr(r, "owned_at", None),
                getattr(r, "completed_at", None),
            ]
        )

    # Auto-fit column widths for readable exports.
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in col_cells:
            val = "" if cell.value is None else str(cell.value)
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(10, max_len + 2), 60
        )

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = (
        f"helpchain_requests_ANON_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.get("/requests/<int:req_id>")
@admin_required
def admin_request_details(req_id: int):
    admin_required_404()
    activities_supported = _table_has_column("request_activities", "volunteer_id")
    if activities_supported:
        req = Request.query.options(
            joinedload(Request.logs), joinedload(Request.activities)
        ).get_or_404(req_id)
    else:
        req = Request.query.options(joinedload(Request.logs)).get_or_404(req_id)
    admin_id = current_user.id
    now = _now_utc()
    latest_actions = []
    if _table_has_column("activity_logs", "id"):
        audit_logs = (
            ActivityLog.query.filter_by(entity_type="request", entity_id=req_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(50)
            .all()
        )
    else:
        audit_logs = []
    if activities_supported:
        latest_actions = (
            RequestActivity.query.filter_by(request_id=req_id)
            .filter(
                RequestActivity.action.in_(
                    ["volunteer_can_help", "volunteer_cant_help"]
                )
            )
            .order_by(RequestActivity.created_at.desc())
            .limit(10)
            .all()
        )
    linked_volunteer_ids = [
        int(v_id)
        for (v_id,) in db.session.query(VolunteerRequestState.volunteer_id)
        .filter(VolunteerRequestState.request_id == req_id)
        .distinct()
        .all()
        if v_id is not None
    ]
    volunteer_engagement = []
    if linked_volunteer_ids:
        linked_volunteers = {
            v.id: v for v in Volunteer.query.filter(Volunteer.id.in_(linked_volunteer_ids)).all()
        }
        for v_id in linked_volunteer_ids:
            score_row = get_volunteer_engagement_score(v_id, now=now)
            v = linked_volunteers.get(v_id)
            display = (
                (getattr(v, "name", None) or getattr(v, "email", None) or f"Volunteer #{v_id}")
                if v is not None
                else f"Volunteer #{v_id}"
            )
            score_row["display"] = display
            volunteer_engagement.append(score_row)
        volunteer_engagement.sort(key=lambda x: (-x["score"], x["volunteer_id"]))

    locked_by = None
    # --- AUTO-LOCK (must happen BEFORE any render_template return) ---
    if req.owner_id is None:
        req.owner_id = admin_id
        req.owned_at = now
        if activities_supported:
            db.session.add(
                RequestActivity(
                    request_id=req.id,
                    actor_admin_id=admin_id,
                    action="lock",
                    old_value="",
                    new_value=str(admin_id),
                    created_at=now,
                )
            )
        db.session.commit()
    elif req.owner_id == admin_id:
        # refresh TTL quietly
        if _lock_expired(req, now):
            req.owned_at = now
            db.session.commit()
    else:
        if _lock_expired(req, now):
            old_owner = req.owner_id
            req.owner_id = admin_id
            req.owned_at = now
            if activities_supported:
                db.session.add(
                    RequestActivity(
                        request_id=req.id,
                        actor_admin_id=admin_id,
                        action="lock",
                        old_value=str(old_owner),
                        new_value=str(admin_id),
                        created_at=now,
                    )
                )
            db.session.commit()
        else:
            locked_by = req.owner_id
            # show locked screen (no commit)
            activities = []
            if activities_supported:
                activities = sorted(
                    (req.activities or []),
                    key=lambda a: a.created_at or datetime.min,
                    reverse=True,
                )[:50]
            interests = (
                VolunteerInterest.query.filter_by(request_id=req_id)
                .order_by(VolunteerInterest.created_at.desc())
                .all()
            )
            return (
                render_template(
                    "admin/request_details.html",
                    req=req,
                    activities=activities,
                    logs=req.logs,
                    STATUS_LABELS_BG=STATUS_LABELS_BG,
                    is_stale=is_stale,
                    interests=interests,
                    latest_actions=latest_actions,
                    volunteer_engagement=volunteer_engagement,
                    audit_logs=audit_logs,
                    is_locked=True,
                    locked_by=locked_by,
                ),
                200,
            )
    is_locked = False
    logs = req.logs  # already sorted by relationship order_by
    activities = []
    if activities_supported:
        activities = sorted(
            (req.activities or []),
            key=lambda a: a.created_at or datetime.min,
            reverse=True,
        )[:50]
    interests = (
        VolunteerInterest.query.filter_by(request_id=req_id)
        .order_by(VolunteerInterest.created_at.desc())
        .all()
    )

    # --- V3: Match & engagement (city-based) ---
    req_city = (getattr(req, "city", "") or "").strip().lower()

    def _norm_city(val: str) -> str:
        return (val or "").strip().lower()

    vols = Volunteer.query.filter_by(is_active=True).all()
    matched_volunteers = [
        v for v in vols if _norm_city(getattr(v, "location", None)) == req_city
    ]
    matched_volunteers = matched_volunteers[:20]
    matched_volunteer_ids = [v.id for v in matched_volunteers]

    notif_rows = []
    if matched_volunteer_ids:
        notif_rows = Notification.query.filter(
            Notification.request_id == req.id,
            Notification.type == "new_match",
            Notification.volunteer_id.in_(matched_volunteer_ids),
        ).all()
    notified_count = len(notif_rows)
    seen_count = sum(1 for n in notif_rows if getattr(n, "is_read", False))

    interest_rows = interests  # already loaded for this request
    interested_ids = {i.volunteer_id for i in interest_rows}
    interested_count = len(interested_ids)

    notif_by_vol = {n.volunteer_id: n for n in notif_rows}
    flags_by_vol = {}
    for v in matched_volunteers:
        n = notif_by_vol.get(v.id)
        flags_by_vol[v.id] = {
            "notified": n is not None,
            "seen": bool(getattr(n, "is_read", False)) if n else False,
            "interested": v.id in interested_ids,
        }

    assigned_volunteer = None
    if getattr(req, "assigned_volunteer_id", None):
        assigned_volunteer = Volunteer.query.get(req.assigned_volunteer_id)

    # Volunteer signals (can/can't help)
    volunteer_signals = (
        VolunteerAction.query.filter_by(request_id=req.id)
        .order_by(VolunteerAction.updated_at.desc())
        .all()
    )
    # Most recent signal for quick, high-visibility admin context.
    last_vol_signal = volunteer_signals[0] if volunteer_signals else None
    signal_vol_ids = [va.volunteer_id for va in volunteer_signals]
    volunteers_map = (
        {
            v.id: v
            for v in Volunteer.query.filter(Volunteer.id.in_(signal_vol_ids)).all()
        }
        if signal_vol_ids
        else {}
    )
    can_help_count = sum(1 for va in volunteer_signals if va.action == "CAN_HELP")
    cant_help_count = sum(1 for va in volunteer_signals if va.action == "CANT_HELP")

    return (
        render_template(
            "admin/request_details.html",
            req=req,
            activities=activities,
            logs=logs,
            STATUS_LABELS_BG=STATUS_LABELS_BG,
            is_stale=is_stale,
            interests=interests,
            is_locked=is_locked,
            locked_by=locked_by,
            matched_volunteers=matched_volunteers,
            matched_count=len(matched_volunteers),
            notified_count=notified_count,
            seen_count=seen_count,
            interested_count=interested_count,
            flags_by_vol=flags_by_vol,
            assigned_volunteer=assigned_volunteer,
            volunteer_signals=volunteer_signals,
            last_vol_signal=last_vol_signal,
            volunteers_map=volunteers_map,
            can_help_count=can_help_count,
            cant_help_count=cant_help_count,
            latest_actions=latest_actions,
            volunteer_engagement=volunteer_engagement,
            audit_logs=audit_logs,
        ),
        200,
    )


@admin_bp.post("/requests/<int:req_id>/unlock", endpoint="admin_request_unlock")
@admin_required
def admin_request_unlock(req_id: int):
    admin_required_404()
    admin_id = _admin_id()
    if not admin_id:
        abort(403)

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

    old_owner = req.owner_id
    if old_owner is not None:
        req.owner_id = None
        req.owned_at = None
        db.session.add(
            RequestActivity(
                request_id=req.id,
                actor_admin_id=admin_id,
                action="unlock",
                old_value=str(old_owner),
                new_value="",
                created_at=_now_utc(),
            )
        )
        db.session.commit()

    flash("Unlocked.", "success")
    return redirect(url_for("admin.admin_request_details", req_id=req_id))


# --- Volunteer interest moderation ---
@admin_bp.post(
    "/requests/<int:req_id>/interests/<int:interest_id>/approve",
    endpoint="admin_interest_approve",
)
@admin_required
def admin_interest_approve(req_id: int, interest_id: int):
    current_app.logger.info(
        "ADMIN_APPROVE HIT req_id=%s interest_id=%s", req_id, interest_id
    )

    admin_required_404()
    admin = current_user
    admin_id = getattr(admin, "id", None)

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

    if _locked_by_other(req, admin_id):
        flash(
            "🔒 Заявката е заключена от друг админ. Може да я отключите ръчно.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    vi = db.session.get(VolunteerInterest, interest_id)
    if not vi or vi.request_id != req_id:
        abort(404)

    if _is_request_locked(req):
        flash(
            "🔒 Заявката е заключена (done/cancelled). Смени статуса, за да отключиш действията.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    old_vi = vi.status
    changed_vi = old_vi != "approved"
    if changed_vi:
        vi.status = "approved"
        db.session.add(
            RequestActivity(
                request_id=req_id,
                actor_admin_id=admin_id,
                action="volunteer_interest_approved",
                old_value=old_vi,
                new_value="approved",
            )
        )

    # Auto transition: open -> in_progress (single log)
    old_rs = req.status
    status_changed = False
    if old_rs == "open":
        req.status = "in_progress"
        _log_status_change_once(req_id, old_rs, req.status, admin_id)
        status_changed = True

    if changed_vi or status_changed:
        current_app.logger.info(
            "BEFORE commit: req.status=%s vi.status=%s", req.status, vi.status
        )
        db.session.commit()
        current_app.logger.info(
            "AFTER commit: req.status=%s vi.status=%s", req.status, vi.status
        )
        flash("Approved.", "success")
    else:
        flash("No changes.", "info")

    return redirect(url_for("admin.admin_request_details", req_id=req_id))


@admin_bp.post(
    "/requests/<int:req_id>/interests/<int:interest_id>/reject",
    endpoint="admin_interest_reject",
)
@admin_required
def admin_interest_reject(req_id: int, interest_id: int):
    admin_required_404()
    admin = current_user
    admin_id = getattr(admin, "id", None)

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

    if _locked_by_other(req, admin_id):
        flash(
            "🔒 Заявката е заключена от друг админ. Може да я отключите ръчно.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    interest = db.session.get(VolunteerInterest, interest_id)
    if not interest or interest.request_id != req_id:
        abort(404)

    if _is_request_locked(req):
        flash(
            "🔒 Заявката е заключена (done/cancelled). Смени статуса, за да отключиш действията.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    old_vi = interest.status
    if old_vi == "rejected":
        flash("No changes.", "info")
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    current_app.logger.info(
        "ADMIN_REJECT HIT req_id=%s interest_id=%s", req_id, interest_id
    )

    interest.status = "rejected"
    db.session.add(
        RequestActivity(
            request_id=req.id,
            actor_admin_id=admin_id,
            action="volunteer_interest_rejected",
            old_value=old_vi,
            new_value="rejected",
        )
    )

    db.session.commit()
    flash("Rejected.", "warning")
    return redirect(url_for("admin.admin_request_details", req_id=req_id))


# --- Assign owner to request ---
@admin_bp.post("/requests/<int:req_id>/assign", endpoint="admin_request_assign")
@login_required
def admin_request_assign(req_id: int):
    req = Request.query.get_or_404(req_id)
    if _locked_by_other(req, getattr(current_user, "id", None)):
        flash(
            "🔒 Заявката е заключена от друг админ. Може да я отключите ръчно.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))
    if _is_request_locked(req):
        flash(
            "This request is locked (done/cancelled). Unlock it by changing status first.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))
    takeover = False
    if req.owner_id and req.owner_id != getattr(current_user, "id", None):
        if getattr(current_user, "role", None) != "super_admin" and not is_stale(req):
            abort(403)
        takeover = True
    old_owner = req.owner_id
    req.owner_id = current_user.id
    req.owned_at = utc_now()
    metric = db.session.query(RequestMetric).filter_by(request_id=req.id).first()
    if metric is None:
        metric = RequestMetric(request_id=req.id)
        db.session.add(metric)
    if metric.time_to_assign is None and req.created_at:
        try:
            metric.time_to_assign = int((utc_now() - req.created_at).total_seconds())
        except Exception:
            pass
    action_name = "takeover" if takeover else "assign"
    reason = None
    if takeover and req.owned_at:
        try:
            hours = (utc_now() - req.owned_at).total_seconds() / 3600
            reason = f"stale: {hours:.1f}h"
        except Exception:
            reason = "stale"
    new_val = (
        f"{current_user.id}" if reason is None else f"{current_user.id} ({reason})"
    )
    log_request_activity(
        req, action_name, old=old_owner, new=new_val, actor_admin_id=current_user.id
    )
    _audit_request(
        req.id,
        action="assign_owner",
        message="Owner assigned",
        old=str(old_owner) if old_owner is not None else None,
        new=str(current_user.id),
    )
    db.session.commit()
    flash("Заявката е assign-ната към теб.", "success")
    next_url = (request.form.get("next") or "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("admin.admin_request_details", req_id=req_id))


@admin_bp.post("/requests/<int:req_id>/unassign", endpoint="admin_request_unassign")
@login_required
def admin_request_unassign(req_id: int):
    req = Request.query.get_or_404(req_id)
    if _locked_by_other(req, getattr(current_user, "id", None)):
        flash(
            "🔒 Заявката е заключена от друг админ. Може да я отключите ръчно.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))
    if _is_request_locked(req):
        flash(
            "This request is locked (done/cancelled). Unlock it by changing status first.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))
    if not can_edit_request(req, current_user):
        abort(403)
    old_owner = req.owner_id
    req.owner_id = None
    req.owned_at = None
    log_request_activity(
        req,
        "unassign",
        old=old_owner,
        new=None,
        actor_admin_id=getattr(current_user, "id", None),
    )
    _audit_request(
        req.id,
        action="unassign_owner",
        message="Owner unassigned",
        old=str(old_owner) if old_owner is not None else None,
        new=None,
    )
    db.session.commit()
    flash("Owner е премахнат.", "info")
    return redirect(url_for("admin.admin_request_details", req_id=req_id))


@admin_bp.post(
    "/requests/<int:req_id>/assign_volunteer/<int:volunteer_id>",
    endpoint="admin_assign_volunteer",
)
@login_required
def admin_assign_volunteer(req_id: int, volunteer_id: int):
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)
    if _is_request_locked(req):
        flash("This request is locked (done/cancelled).", "warning")
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    req.assigned_volunteer_id = volunteer_id
    log_request_activity(
        req,
        "assign_volunteer",
        old=getattr(req, "assigned_volunteer_id", None),
        new=volunteer_id,
        actor_admin_id=getattr(current_user, "id", None),
    )
    db.session.commit()
    flash("Assigned to volunteer.", "success")
    return redirect(url_for("admin.admin_request_details", req_id=req.id))


@admin_bp.post(
    "/requests/<int:req_id>/unassign_volunteer", endpoint="admin_unassign_volunteer"
)
@login_required
def admin_unassign_volunteer(req_id: int):
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)
    old_val = getattr(req, "assigned_volunteer_id", None)
    req.assigned_volunteer_id = None
    log_request_activity(
        req,
        "unassign_volunteer",
        old=old_val,
        new=None,
        actor_admin_id=getattr(current_user, "id", None),
    )
    db.session.commit()
    flash("Volunteer unassigned.", "info")
    return redirect(url_for("admin.admin_request_details", req_id=req.id))


@admin_bp.post("/requests/<int:req_id>/nudge", endpoint="admin_request_nudge")
@login_required
def admin_request_nudge(req_id: int):
    admin_required_404()
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)

    volunteer_id = getattr(req, "assigned_volunteer_id", None)
    if not volunteer_id:
        flash("No assigned volunteer to nudge.", "warning")
        return redirect(request.referrer or url_for("admin.admin_requests"))

    created = send_nudge_notification(
        request_id=req.id,
        volunteer_id=int(volunteer_id),
        actor_admin_id=getattr(current_user, "id", None),
    )
    if created:
        flash("Nudge sent.", "success")
    else:
        flash("Nudge suppressed (recently sent).", "info")
    return redirect(request.referrer or url_for("admin.admin_requests"))


@admin_bp.post("/requests/<int:req_id>/delete", endpoint="admin_request_delete")
@login_required
def admin_request_delete(req_id: int):
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)

    if not getattr(req, "is_archived", False):
        flash(
            "Archive the request first. Only archived requests can be deleted.",
            "warning",
        )
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    if getattr(req, "deleted_at", None) is None:
        req.deleted_at = utc_now()
        req.is_archived = True
        if getattr(req, "archived_at", None) is None:
            req.archived_at = req.deleted_at
        log_request_activity(
            req,
            "delete",
            old=None,
            new=str(req.deleted_at),
            actor_admin_id=getattr(current_user, "id", None),
        )
        db.session.commit()
        flash("Request moved to Deleted.", "success")

    return redirect(url_for("admin.admin_request_details", req_id=req.id))


@admin_bp.post(
    "/requests/<int:req_id>/restore-deleted", endpoint="admin_request_restore_deleted"
)
@login_required
def admin_request_restore_deleted(req_id: int):
    req = Request.query.get_or_404(req_id)
    if not can_edit_request(req, current_user):
        abort(403)

    if getattr(req, "deleted_at", None) is not None:
        old = req.deleted_at
        req.deleted_at = None
        req.is_archived = True
        if getattr(req, "archived_at", None) is None:
            req.archived_at = utc_now()
        log_request_activity(
            req,
            "restore_deleted",
            old=str(old),
            new=None,
            actor_admin_id=getattr(current_user, "id", None),
        )
        db.session.commit()
        flash("Request restored from Deleted (kept archived).", "success")

    return redirect(url_for("admin.admin_request_details", req_id=req.id))


@admin_bp.post("/requests/<int:req_id>/note")
@login_required
def admin_request_add_note(req_id: int):
    req = Request.query.get_or_404(req_id)
    note = (request.form.get("note") or "").strip()
    if not note:
        flash("Note is empty.", "warning")
        return redirect(url_for("admin.admin_request_details", req_id=req.id))
    if len(note) > 2000:
        flash("Note is too long (max 2000 chars).", "danger")
        return redirect(url_for("admin.admin_request_details", req_id=req.id))

    log_request_activity(
        req,
        "note",
        old=None,
        new=note,
        actor_admin_id=getattr(current_user, "id", None),
    )
    _audit_request(
        req.id,
        action="note_add",
        message="Admin note added",
    )
    db.session.commit()
    flash("Note added.", "success")
    return redirect(url_for("admin.admin_request_details", req_id=req.id))


# --- ALIASES (temporary, to keep templates stable) ---
@admin_bp.get("/requests/<int:req_id>/status")
@login_required
def admin_request_status_get_alias(req_id: int):
    # Status is edited inside details page; redirect there.
    return redirect(url_for("admin.admin_request_details", req_id=req_id), code=302)


@admin_bp.get("/requests/<int:req_id>/notes")
@login_required
def admin_request_notes_get_alias(req_id: int):
    return redirect(url_for("admin.admin_request_details", req_id=req_id), code=302)


@admin_bp.post("/requests/<int:req_id>/notes")
@login_required
def admin_request_notes_post_alias(req_id: int):
    # Reuse existing note handler (/note) without changing templates.
    return admin_request_add_note(req_id)


@admin_bp.get("/professional-leads")
@login_required
@admin_required
def admin_professional_leads():
    q = (request.args.get("q") or "").strip()
    profession = (request.args.get("profession") or "").strip()
    city = (request.args.get("city") or "").strip()
    status = (request.args.get("status") or "").strip().lower()
    status_choices = ["new", "contacted", "qualified", "rejected"]

    query = ProfessionalLead.query

    if q:
        like = f"%{q.lower()}%"
        query = query.filter(ProfessionalLead.email.ilike(like))

    if profession:
        query = query.filter(ProfessionalLead.profession == profession)

    if city:
        query = query.filter(ProfessionalLead.city.ilike(f"%{city}%"))

    if status:
        query = query.filter(func.lower(ProfessionalLead.status) == status)

    leads = (
        query.order_by(ProfessionalLead.created_at.desc(), ProfessionalLead.id.desc())
        .limit(200)
        .all()
    )

    professions = (
        ProfessionalLead.query.with_entities(ProfessionalLead.profession)
        .distinct()
        .order_by(ProfessionalLead.profession.asc())
        .all()
    )
    professions = [p[0] for p in professions if p and p[0]]

    return render_template(
        "admin/professional_leads.html",
        leads=leads,
        q=q,
        profession=profession,
        city=city,
        status=status,
        status_choices=status_choices,
        professions=professions,
    ), 200


@admin_bp.post("/professional-leads/<int:lead_id>/contacted")
@login_required
@admin_required
def admin_professional_lead_mark_contacted(lead_id: int):
    lead = ProfessionalLead.query.get_or_404(lead_id)
    if (lead.status or "").lower() != "contacted":
        lead.status = "contacted"
        if not lead.contacted_at:
            lead.contacted_at = datetime.now(UTC)
        db.session.commit()
        flash(f"Lead #{lead.id} marked as contacted.", "success")
    return redirect(url_for("admin.admin_professional_leads"), code=303)


@admin_bp.route("/professional-leads/<int:lead_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_professional_lead_detail(lead_id: int):
    lead = ProfessionalLead.query.get_or_404(lead_id)
    status_choices = ["new", "contacted", "qualified", "rejected"]

    if request.method == "POST":
        status = (request.form.get("status") or "").strip().lower()
        notes = (request.form.get("notes") or "").strip()
        if status not in status_choices:
            status = "new"

        lead.status = status
        lead.notes = notes or None
        if status == "contacted" and not lead.contacted_at:
            lead.contacted_at = datetime.now(UTC)
        elif status != "contacted":
            lead.contacted_at = None

        db.session.commit()
        flash(f"Lead #{lead.id} updated.", "success")
        return redirect(
            url_for("admin.admin_professional_lead_detail", lead_id=lead.id), code=303
        )

    return render_template(
        "admin/professional_lead_detail.html",
        lead=lead,
        status_choices=status_choices,
    ), 200


@admin_bp.get("/professionnels/leads")
@login_required
@admin_required
def admin_professionnels_leads():
    return redirect(url_for("admin.admin_professional_leads"), code=302)


@admin_bp.get("/pro-access")
@login_required
@admin_required
def admin_pro_access_list():
    status = (request.args.get("status") or "new").strip().lower()
    if status not in PRO_ACCESS_STATUSES and status != "all":
        status = "new"

    query = ProAccessRequest.query
    if status != "all":
        query = query.filter(ProAccessRequest.status == status)

    rows = (
        query.order_by(ProAccessRequest.created_at.desc(), ProAccessRequest.id.desc())
        .limit(500)
        .all()
    )

    counts = {
        "new": ProAccessRequest.query.filter_by(status="new").count(),
        "reviewed": ProAccessRequest.query.filter_by(status="reviewed").count(),
        "approved": ProAccessRequest.query.filter_by(status="approved").count(),
        "rejected": ProAccessRequest.query.filter_by(status="rejected").count(),
        "all": ProAccessRequest.query.count(),
    }

    return render_template(
        "admin/pro_access_list.html",
        rows=rows,
        status=status,
        counts=counts,
    ), 200


@admin_bp.get("/audit")
@login_required
@admin_required
def admin_audit():
    entity = (request.args.get("entity") or "all").strip().lower()
    action = (request.args.get("action") or "all").strip().lower()
    q = (request.args.get("q") or "").strip()
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 100

    if not _table_has_column("activity_logs", "id"):
        return render_template(
            "admin/audit.html",
            rows=[],
            pagination=None,
            entity=entity,
            action=action,
            q=q,
            entities=[],
            actions=[],
            total=0,
        ), 200

    base = ActivityLog.query
    if entity != "all":
        base = base.filter(ActivityLog.entity_type == entity)
    if action != "all":
        base = base.filter(ActivityLog.action == action)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(
                ActivityLog.message.ilike(like),
                ActivityLog.actor_email.ilike(like),
                ActivityLog.old_value.ilike(like),
                ActivityLog.new_value.ilike(like),
            )
        )

    base = base.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
    pagination = base.paginate(page=page, per_page=per_page, error_out=False)
    rows = pagination.items

    entities = [
        r[0]
        for r in db.session.query(ActivityLog.entity_type)
        .filter(ActivityLog.entity_type.isnot(None))
        .distinct()
        .order_by(ActivityLog.entity_type.asc())
        .all()
        if r and r[0]
    ]
    actions_q = db.session.query(ActivityLog.action).filter(ActivityLog.action.isnot(None))
    if entity != "all":
        actions_q = actions_q.filter(ActivityLog.entity_type == entity)
    actions = [r[0] for r in actions_q.distinct().order_by(ActivityLog.action.asc()).all() if r and r[0]]

    return render_template(
        "admin/audit.html",
        rows=rows,
        pagination=pagination,
        entity=entity,
        action=action,
        q=q,
        entities=entities,
        actions=actions,
        total=int(pagination.total or 0),
    ), 200


@admin_bp.get("/pro-access/<int:pro_id>")
@login_required
@admin_required
def admin_pro_access_detail(pro_id: int):
    row = ProAccessRequest.query.get_or_404(pro_id)
    if _table_has_column("activity_logs", "id"):
        audit_logs = (
            ActivityLog.query.filter_by(entity_type="pro_access", entity_id=pro_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(50)
            .all()
        )
    else:
        audit_logs = []
    return render_template(
        "admin/pro_access_detail.html",
        row=row,
        audit_logs=audit_logs,
    ), 200


def _pro_access_set_status(row: ProAccessRequest, new_status: str, note: str | None = None):
    old_status = (row.status or "").strip().lower() or None
    row.status = new_status
    row.reviewed_at = utc_now()
    row.reviewed_by = (
        getattr(current_user, "email", None)
        or getattr(current_user, "username", None)
        or "admin"
    )
    if note is not None:
        row.admin_notes = note
    _audit_pro_access(
        row.id,
        action="status_change",
        message="Pro access status updated",
        old=old_status,
        new=new_status,
        meta={"has_admin_notes": bool(note)},
    )


@admin_bp.post("/pro-access/<int:pro_id>/review")
@login_required
@admin_required
def admin_pro_access_review(pro_id: int):
    row = ProAccessRequest.query.get_or_404(pro_id)
    note = (request.form.get("admin_notes") or "").strip() or None
    _pro_access_set_status(row, "reviewed", note)
    db.session.commit()
    flash("Marked as reviewed.", "success")
    return redirect(url_for("admin.admin_pro_access_detail", pro_id=pro_id), code=303)


@admin_bp.post("/pro-access/<int:pro_id>/approve")
@login_required
@admin_required
def admin_pro_access_approve(pro_id: int):
    row = ProAccessRequest.query.get_or_404(pro_id)
    note = (request.form.get("admin_notes") or "").strip() or None
    _pro_access_set_status(row, "approved", note)
    db.session.commit()
    flash("Approved.", "success")
    return redirect(url_for("admin.admin_pro_access_detail", pro_id=pro_id), code=303)


@admin_bp.post("/pro-access/<int:pro_id>/reject")
@login_required
@admin_required
def admin_pro_access_reject(pro_id: int):
    row = ProAccessRequest.query.get_or_404(pro_id)
    note = (request.form.get("admin_notes") or "").strip() or None
    _pro_access_set_status(row, "rejected", note)
    db.session.commit()
    flash("Rejected.", "success")
    return redirect(url_for("admin.admin_pro_access_detail", pro_id=pro_id), code=303)
