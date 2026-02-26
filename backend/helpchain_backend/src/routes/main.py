import hashlib
import math
import re
import secrets
import time
from collections import deque
from datetime import UTC, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse

from babel.dates import format_timedelta
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import get_locale as babel_get_locale
from flask_babel import gettext as _
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_required, logout_user
from markupsafe import Markup, escape
from sqlalchemy import desc, func, or_
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from ..authz import can_view_request
from ..category_data import ALIASES, CATEGORIES, COMMON
from ..extensions import csrf, limiter
from ..models import (
    Notification,
    ProfessionalLead,
    Request,
    RequestActivity,
    Volunteer,
    VolunteerAction,
    canonical_role,
    current_structure,
    db,
    utc_now,
)
from ..models.magic_link_token import MagicLinkToken
from ..models.volunteer_interest import VolunteerInterest
from ..notifications.inapp import (
    ensure_new_match_notifications,
    mark_notification_opened,
    mark_request_seen_for_volunteer,
)
from ..security_logging import log_security_event
from ..services.matching_v1 import dismiss_for as match_dismiss_for
from ..services.matching_v1 import get_matched_requests_v1
from ..services.matching_v1 import mark_seen as match_mark_seen
from ..statuses import normalize_request_status

COUNTRIES_SUPPORTED = ["FR", "CH", "CA", "BG"]

main_bp = Blueprint("main", __name__)


def _current_structure_id():
    return int(current_structure().id)


def _scope_requests(query):
    return query.filter(Request.structure_id == _current_structure_id())


def scoped_requests_query():
    return _scope_requests(Request.query)


def get_scoped_request_or_404(req_id: int):
    return scoped_requests_query().filter(Request.id == req_id).first_or_404()


def email_or_ip_key():
    """Prefer per-email throttling; fall back to IP for anonymous abuse control."""
    email = (request.form.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    return get_remote_address()


_IN_MEMORY_RL: dict[str, deque] = {}


def _client_ip() -> str:
    # Minimal proxy awareness; real deployments should rely on ProxyFix + remote_addr.
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return xff or (request.remote_addr or "unknown")


def _rate_limit_allow(key: str, limit: int, window_sec: int) -> bool:
    """
    MVP in-memory rate limit with a sliding time window.
    Returns True when request is allowed, False when rate-limited.

    Anti-enumeration: call sites should return a generic OK view on False.
    """
    now = time.time()
    q = _IN_MEMORY_RL.get(key)
    if q is None:
        q = deque()
        _IN_MEMORY_RL[key] = q

    cutoff = now - float(window_sec)
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= int(limit):
        return False
    q.append(now)
    return True


def _rate_limit_check(key: str, limit: int, window_sec: int) -> tuple[bool, int]:
    """
    Sliding-window limiter with retry_after support.
    Returns (allowed, retry_after_seconds).
    """
    now = time.time()
    q = _IN_MEMORY_RL.get(key)
    if q is None:
        q = deque()
        _IN_MEMORY_RL[key] = q

    cutoff = now - float(window_sec)
    while q and q[0] < cutoff:
        q.popleft()

    if len(q) >= int(limit):
        oldest = q[0]
        retry_after = int(max(1, math.ceil(float(window_sec) - (now - oldest))))
        return False, retry_after

    q.append(now)
    return True, 0


def has_control_chars(text: str) -> bool:
    """Detect non-printable control chars (excluding common whitespace)."""
    if not text:
        return False
    return any(ord(ch) < 32 and ch not in ("\t", "\n", "\r") for ch in text)


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    """Normalize datetimes to naive UTC for safe comparisons across legacy rows."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


# --- Helpers ---
def normalize_list(value):
    """Normalize comma- or list-based values to a lowercase set."""
    if not value:
        return set()
    if isinstance(value, list):
        return {v.strip().lower() for v in value if v and str(v).strip()}
    return {v.strip().lower() for v in str(value).split(",") if v.strip()}


def is_safe_url(target: str) -> bool:
    """Ensure redirects stay on same host."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def get_safe_next(default_endpoint: str):
    nxt = request.args.get("next")
    if nxt and is_safe_url(nxt):
        return nxt
    return default_endpoint


def _safe_volunteer_next_path(candidate: str | None) -> str | None:
    """Allow only local volunteer paths for post-magic-link redirects."""
    c = (candidate or "").strip()
    if not c:
        return None
    if not is_safe_url(c):
        return None
    if not c.startswith("/volunteer/"):
        return None
    return c


REMOTE_MARKERS = {
    "remote",
    "online",
    "en ligne",
    "à distance",
    "a distance",
    "zoom",
    "google meet",
    "teams",
    "video",
    "онлайн",
    "дистанционно",
    "по телефон",
    "телефон",
}


def is_remote_request(req) -> bool:
    """Heuristic remote flag based on text fields (no is_remote column)."""
    text = " ".join(
        [
            (getattr(req, "location_text", None) or ""),
            (getattr(req, "message", None) or ""),
            (getattr(req, "description", None) or ""),
        ]
    ).lower()

    if any(marker in text for marker in REMOTE_MARKERS):
        return True

    city = (getattr(req, "city", None) or "").strip()
    loc_text = (getattr(req, "location_text", None) or "").strip()
    if not city and loc_text:
        return True

    return False


def is_request_matching_volunteer(
    request_obj, volunteer_obj, interested_request_ids: set[int] | None = None
):
    """MVP matching (V2.2.A): status open + volunteer active + profile complete + not already interested."""
    if not request_obj or not volunteer_obj:
        return False

    if (getattr(request_obj, "status", "") or "").lower() != "open":
        return False

    if not getattr(volunteer_obj, "is_active", False):
        return False

    # profile completeness (location + availability)
    if not (
        getattr(volunteer_obj, "location", None)
        and getattr(volunteer_obj, "availability", None)
    ):
        return False

    # exclude assigned/archived/deleted
    if getattr(request_obj, "assigned_volunteer_id", None) is not None:
        return False
    if getattr(request_obj, "is_archived", False):
        return False
    if getattr(request_obj, "deleted_at", None) is not None:
        return False

    if (
        interested_request_ids
        and getattr(request_obj, "id", None) in interested_request_ids
    ):
        return False

    # Geo/skills matching postponed (later versions)
    return True


def require_volunteer_login(fn):
    """Minimal access control using session flag (non-Flask-Login)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("volunteer_id"):
            return redirect(
                url_for("main.become_volunteer", next=request.path), code=303
            )
        return fn(*args, **kwargs)

    return wrapper


def _current_volunteer():
    vid = session.get("volunteer_id")
    if not vid:
        return None
    try:
        return db.session.get(Volunteer, int(vid))
    except Exception:
        return None


# ✅ url_lang + safe_url_for in ALL templates rendered by this blueprint
@main_bp.app_context_processor
def inject_template_helpers():
    def url_lang(endpoint: str, **values):
        return url_for(endpoint, **values)

    def safe_url_for(endpoint: str, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return "#"

    def time_ago(dt):
        if not dt:
            return ""
        try:
            delta = datetime.utcnow() - dt.replace(tzinfo=None)
        except Exception:
            return ""
        return format_timedelta(
            delta, add_direction=True, locale=str(babel_get_locale())
        )

    def og_image_url(filename: str | None = None):
        fallback_rel = "img/og-home-1200x630.jpg"
        try:
            candidate = (filename or "").strip()
            if candidate:
                candidate = candidate.replace("\\", "/")
                candidate_rel = (
                    candidate if candidate.startswith("img/") else f"img/{candidate}"
                )
                candidate_path = Path(current_app.static_folder) / Path(candidate_rel)
                if candidate_path.is_file():
                    return url_for("static", filename=candidate_rel, _external=True)
        except Exception:
            pass
        return url_for("static", filename=fallback_rel, _external=True)

    return {
        "url_lang": url_lang,
        "safe_url_for": safe_url_for,
        "time_ago": time_ago,
        "og_image_url": og_image_url,
    }


@main_bp.route("/", methods=["GET"])
def index():
    """Главна страница"""
    latest_requests = []
    active_count = 0
    try:
        latest_requests = (
            scoped_requests_query()
            .filter(Request.deleted_at.is_(None))
            .filter(Request.is_archived.is_(False))
            .order_by(Request.created_at.desc())
            .limit(6)
            .all()
        )
        active_count = (
            db.session.query(func.count(Request.id))
            .filter(Request.structure_id == _current_structure_id())
            .filter(Request.deleted_at.is_(None))
            .filter(Request.is_archived.is_(False))
            .scalar()
        ) or 0
    except Exception as e:
        current_app.logger.warning("Home latest_requests skipped: %s", e)
        latest_requests = []
        active_count = 0

    now_utc_naive = _to_utc_naive(utc_now())

    def is_new_request(req) -> bool:
        created = _to_utc_naive(getattr(req, "created_at", None))
        if not created or not now_utc_naive:
            return False
        return (now_utc_naive - created) <= timedelta(hours=24)

    return (
        render_template(
            "home_new_slim.html",
            latest_requests=latest_requests,
            active_count=active_count,
            is_new_request=is_new_request,
        ),
        200,
    )


@main_bp.post("/events")
@csrf.exempt
@limiter.limit("120 per minute")
def events_collect():
    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    props = data.get("props") or {}
    if not event:
        return jsonify({"ok": False}), 400
    try:
        current_app.logger.info("[EVENT] %s %s", event, props)
    except Exception:
        pass
    return jsonify({"ok": True}), 200


def _emit_event(event: str, props: dict | None = None) -> None:
    """Internal telemetry helper aligned with /events payload shape."""
    if not event:
        return
    try:
        current_app.logger.info("[EVENT] %s %s", event, props or {})
    except Exception:
        pass


@main_bp.post("/csp-report")
@csrf.exempt
def csp_report():
    # Browsers may send application/csp-report or application/json.
    data = request.get_json(silent=True) or {}
    current_app.logger.warning("[CSP-REPORT] %s", data)
    return ("", 204)


@main_bp.route("/logout", methods=["GET", "POST"], endpoint="logout")
def logout():
    """Unified logout for Flask-Login users (admin/front) and volunteer session."""
    # If admin session is active, hand off to admin logout (keeps MFA cleanup)
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.admin_logout"))

    try:
        logout_user()
    except Exception:
        pass

    # Clear all session data to avoid stale logins
    try:
        session.clear()
    except Exception:
        # Fallback: pop known keys
        for key in list(session.keys()):
            session.pop(key, None)

    resp = redirect(url_for("main.index"))

    # Proactively drop remember/session cookies if present
    try:
        sess_cookie = current_app.config.get("SESSION_COOKIE_NAME", "session")
        resp.delete_cookie(sess_cookie, path="/")
    except Exception:
        pass
    try:
        remember_cookie = current_app.config.get(
            "REMEMBER_COOKIE_NAME", "remember_token"
        )
        resp.delete_cookie(remember_cookie, path="/")
    except Exception:
        pass

    return resp


@main_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    role = getattr(current_user, "role_canon", None) or canonical_role(
        getattr(current_user, "role", None)
    )

    if role in ("admin", "superadmin"):
        return redirect(url_for("admin.admin_requests"))

    if role == "requester":
        my_requests = (
            scoped_requests_query()
            .filter(Request.user_id == current_user.id)
            .populate_existing()
            .order_by(desc(Request.created_at))
            .limit(20)
            .all()
        )
        counts = dict(
            ((s or "open"), c)
            for s, c in db.session.query(Request.status, func.count(Request.id))
            .filter(Request.structure_id == _current_structure_id())
            .filter(Request.user_id == current_user.id)
            .group_by(Request.status)
            .all()
        )
        kpi = {
            "open": counts.get("open", 0),
            "in_progress": counts.get("in_progress", 0),
            "done": counts.get("done", 0),
            "cancelled": counts.get("cancelled", 0),
        }
        return render_template(
            "dashboard_requester.html", my_requests=my_requests, kpi=kpi
        )

    if role in ("volunteer", "professional"):
        assigned = (
            scoped_requests_query()
            .filter(Request.owner_id == current_user.id)
            .populate_existing()
            .order_by(desc(Request.owned_at), desc(Request.created_at))
            .limit(20)
            .all()
        )
        for r in assigned:
            try:
                r.status_norm = normalize_request_status(getattr(r, "status", None))
            except Exception:
                r.status_norm = getattr(r, "status", None)
        counts = dict(
            ((s or "open"), c)
            for s, c in db.session.query(Request.status, func.count(Request.id))
            .filter(Request.structure_id == _current_structure_id())
            .filter(Request.owner_id == current_user.id)
            .group_by(Request.status)
            .all()
        )
        kpi = {
            "open": counts.get("open", 0),
            "in_progress": counts.get("in_progress", 0),
            "done": counts.get("done", 0),
            "cancelled": counts.get("cancelled", 0),
        }
        return render_template("dashboard_helper.html", assigned=assigned, kpi=kpi)

    return render_template("dashboard_unknown_role.html", role=role), 403


@main_bp.get("/profile")
def profile():
    # Authenticated users: route by role
    if getattr(current_user, "is_authenticated", False):
        role = getattr(current_user, "role_canon", None) or canonical_role(
            getattr(current_user, "role", None)
        )
        if role in ("admin", "superadmin"):
            return redirect(url_for("admin.admin_requests"))
        if role in ("volunteer", "professional"):
            return redirect(url_for("main.dashboard"))

    # Requester via session-stored email
    requester_email = (session.get("requester_email") or "").strip().lower()
    if not requester_email:
        return redirect(url_for("main.submit_request"))

    my_requests = (
        scoped_requests_query()
        .filter(func.lower(Request.email) == requester_email)
        .order_by(desc(Request.created_at))
        .limit(20)
        .all()
    )
    rows = (
        db.session.query(Request.status, func.count(Request.id))
        .filter(Request.structure_id == _current_structure_id())
        .filter(func.lower(Request.email) == requester_email)
        .group_by(Request.status)
        .all()
    )
    counts = {(s or "open"): c for s, c in rows}
    kpi = {
        "open": counts.get("open", 0),
        "in_progress": counts.get("in_progress", 0),
        "done": counts.get("done", 0),
        "cancelled": counts.get("cancelled", 0),
    }
    return render_template(
        "profile_requester.html",
        kpi=kpi,
        my_requests=my_requests,
        requester_email=requester_email,
    )


@main_bp.get("/requester/logout")
def requester_logout():
    session.pop("requester_email", None)
    flash(_("Your session has been cleared."), "info")
    return redirect(url_for("main.submit_request"))


@main_bp.get("/auth/magic/<token>")
def magic_link_consume(token: str):
    token_hash = _sha256_hex(token)

    try:
        ml = MagicLinkToken.query.filter_by(token_hash=token_hash).first()
    except OperationalError:
        # DB not migrated yet (magic_link_tokens table missing). Fall back to legacy flow.
        db.session.rollback()
        ml = None

    # Legacy compatibility (/r/<token> previously hashed into requests.requester_token_hash).
    if ml is None:
        legacy_req = (
            scoped_requests_query()
            .filter(Request.requester_token_hash == token_hash)
            .order_by(desc(Request.created_at))
            .first()
        )
        if not legacy_req:
            return render_template("magic_link_invalid.html"), 200

        created_at = getattr(legacy_req, "requester_token_created_at", None)
        # If legacy token has no timestamp, treat as invalid to avoid indefinite reuse.
        if not created_at:
            return render_template("magic_link_invalid.html"), 200

        expires_at = _to_utc_naive(created_at + timedelta(minutes=15))
        now = _to_utc_naive(utc_now())
        if now > expires_at:
            return render_template("magic_link_invalid.html"), 200

        # If the new table isn't available yet, keep legacy behavior (no single-use).
        try:
            _ = MagicLinkToken.__table__
        except Exception:
            session["requester_email"] = (
                (getattr(legacy_req, "email", "") or "").strip().lower()
            )
            session["requester_authenticated"] = True
            if getattr(legacy_req, "id", None):
                session["last_request_id"] = int(legacy_req.id)
            return redirect(url_for("main.profile"), code=303)

        try:
            ml = MagicLinkToken(
                token_hash=token_hash,
                purpose="request",
                email=(getattr(legacy_req, "email", "") or "").strip().lower(),
                request_id=getattr(legacy_req, "id", None),
                expires_at=expires_at,
            )
            db.session.add(ml)
            db.session.commit()
        except Exception:
            # Concurrent consume may have inserted the token already.
            db.session.rollback()
            ml = MagicLinkToken.query.filter_by(token_hash=token_hash).first()
            if ml is None:
                return render_template("magic_link_invalid.html"), 200

    now = _to_utc_naive(utc_now())
    expires_at = _to_utc_naive(ml.expires_at)
    if expires_at is None or now > expires_at:
        return render_template("magic_link_invalid.html"), 200

    # Single-use, race-safe: claim the token only if it's unused and unexpired.
    try:
        claimed = (
            MagicLinkToken.query.filter_by(token_hash=token_hash, used_at=None)
            .filter(MagicLinkToken.expires_at >= now)
            .update(
                {
                    MagicLinkToken.used_at: now,
                    MagicLinkToken.used_ip: _client_ip(),
                    MagicLinkToken.used_ua: (request.headers.get("User-Agent") or "")[
                        :255
                    ],
                }
            )
        )
    except OperationalError:
        db.session.rollback()
        return render_template("magic_link_invalid.html"), 200
    if not claimed:
        db.session.rollback()
        return render_template("magic_link_invalid.html"), 200
    db.session.commit()

    # Reload to get purpose/email/request_id.
    ml = MagicLinkToken.query.filter_by(token_hash=token_hash).first()
    if ml is None:
        return render_template("magic_link_invalid.html"), 200

    if ml.purpose == "request":
        # Requester passwordless session (minimal)
        session["requester_email"] = (ml.email or "").strip().lower()
        session["requester_authenticated"] = True
        if ml.request_id:
            session["last_request_id"] = int(ml.request_id)
        return redirect(url_for("main.profile"), code=303)

    if ml.purpose == "volunteer":
        email = (ml.email or "").strip().lower()

        # Avoid cross-role session bleed (admin/requester/etc.). Preserve locale if present.
        lang = session.get("lang")
        session.clear()
        if lang:
            session["lang"] = lang

        # Find-or-create the volunteer record (MVP-safe).
        v = Volunteer.query.filter(Volunteer.email.ilike(email)).first()
        if not v:
            v = Volunteer(email=email, is_active=True)
            db.session.add(v)
            db.session.commit()

        # This is what @require_volunteer_login expects.
        session["volunteer_id"] = int(v.id)
        session["volunteer_logged_in"] = True  # legacy compatibility
        session["just_logged_in"] = True

        target = _safe_volunteer_next_path(session.pop("volunteer_next", None))
        if not target:
            target = url_for("main.volunteer_dashboard")
        return redirect(target, code=303)

    return render_template("magic_link_invalid.html"), 200


@main_bp.get("/r/<token>")
def magic_link_alias(token: str):
    # Alias for older links and for habit; canonical handler lives at /auth/magic/<token>.
    return redirect(url_for("main.magic_link_consume", token=token), code=302)


@main_bp.get("/set-lang/<lang>")
def set_lang_switch(lang):
    lang = (lang or "").lower().strip()
    if lang not in ("bg", "fr", "en"):
        abort(404)

    session["lang"] = lang
    session.modified = True

    next_url = request.referrer or url_for("main.index")
    try:
        ref_host = urlparse(request.host_url).netloc
        target_host = urlparse(next_url).netloc
        if ref_host != target_host:
            next_url = url_for("main.index")
    except Exception:
        next_url = url_for("main.index")

    resp = make_response(redirect(next_url))
    resp.set_cookie("hc_lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@main_bp.get("/lang/<locale>")
def set_lang(locale):
    locale = (locale or "").lower()
    if locale not in ("bg", "fr", "en"):
        abort(404)

    session["lang"] = locale
    session.modified = True
    next_url = request.args.get("next") or url_for("main.index")
    try:
        ref_host = urlparse(request.host_url).netloc
        target_host = urlparse(next_url).netloc
        if target_host and ref_host != target_host:
            next_url = url_for("main.index")
    except Exception:
        next_url = url_for("main.index")

    resp = make_response(redirect(next_url))
    resp.set_cookie("hc_lang", locale, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@main_bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("search_results.html", q="", results=None), 200

    q_like = f"%{q}%"
    q_low = q.lower()
    pattern = re.compile(re.escape(q), re.IGNORECASE)

    def highlight_text(text: str) -> Markup | str:
        raw = (text or "").strip()
        if not raw:
            return ""
        last = 0
        chunks = []
        for match in pattern.finditer(raw):
            chunks.append(escape(raw[last : match.start()]))
            chunks.append(Markup("<mark>"))
            chunks.append(escape(match.group(0)))
            chunks.append(Markup("</mark>"))
            last = match.end()
        if not chunks:
            return escape(raw)
        chunks.append(escape(raw[last:]))
        return Markup("").join(chunks)

    def score(item: dict) -> int:
        title = (item.get("title") or "").lower()
        subtitle = (item.get("subtitle") or "").lower()
        snippet = (item.get("snippet") or "").lower()
        if title == q_low:
            return 0
        if title.startswith(q_low):
            return 1
        if q_low in title:
            return 2
        if q_low in subtitle:
            return 3
        if q_low in snippet:
            return 4
        return 5

    def finalize(items: list[dict]) -> list[dict]:
        ranked = sorted(items, key=score)
        final = []
        for item in ranked:
            final.append(
                {
                    "title": highlight_text(item.get("title")),
                    "url": item.get("url") or "#",
                    "subtitle": highlight_text(item.get("subtitle")),
                    "snippet": highlight_text(item.get("snippet")),
                }
            )
        return final

    results: dict[str, list[dict]] = {
        "requests": [],
        "categories": [],
        "professionals": [],
    }

    try:
        req_rows = (
            scoped_requests_query().filter(
                Request.deleted_at.is_(None),
                Request.is_archived.is_(False),
                or_(
                    Request.title.ilike(q_like),
                    Request.description.ilike(q_like),
                    Request.message.ilike(q_like),
                    Request.city.ilike(q_like),
                    Request.category.ilike(q_like),
                ),
            )
            .order_by(desc(Request.created_at))
            .limit(20)
            .all()
        )
        for row in req_rows:
            results["requests"].append(
                {
                    "title": row.title or _("Request"),
                    "url": url_for("main.request_public", req_id=row.id),
                    "subtitle": row.city or row.category or "",
                    "snippet": (row.description or row.message or "")[:180],
                }
            )
    except Exception as exc:
        current_app.logger.warning("Search requests skipped: %s", exc)

    try:
        cat_hits = []
        for slug, meta in CATEGORIES.items():
            title = (
                meta.get("title")
                or meta.get("label")
                or meta.get("content", {}).get("title", {}).get("fr")
                or meta.get("content", {}).get("title", {}).get("en")
                or meta.get("content", {}).get("title", {}).get("bg")
                or slug
            )
            description_text = (
                meta.get("description")
                or meta.get("desc")
                or meta.get("content", {}).get("intro", {}).get("fr")
                or meta.get("content", {}).get("intro", {}).get("en")
                or meta.get("content", {}).get("intro", {}).get("bg")
                or ""
            )

            hay = f"{slug} {title} {description_text}".lower()
            if q_low in hay:
                cat_hits.append(
                    {
                        "title": title,
                        "url": url_for("main.category_help", category=slug),
                        "subtitle": "Catégorie",
                        "snippet": description_text[:160],
                    }
                )

        results["categories"] = sorted(cat_hits[:18], key=score)
    except Exception as exc:
        current_app.logger.warning("Search categories skipped: %s", exc)

    try:
        pro_rows = (
            ProfessionalLead.query.filter(
                or_(
                    ProfessionalLead.full_name.ilike(q_like),
                    ProfessionalLead.profession.ilike(q_like),
                    ProfessionalLead.organization.ilike(q_like),
                    ProfessionalLead.city.ilike(q_like),
                    ProfessionalLead.message.ilike(q_like),
                )
            )
            .order_by(desc(ProfessionalLead.created_at))
            .limit(12)
            .all()
        )
        for pro in pro_rows:
            subtitle_parts = [pro.profession or "", pro.city or ""]
            results["professionals"].append(
                {
                    "title": pro.full_name or pro.organization or pro.email,
                    "url": url_for("main.professionnels", q=q),
                    "subtitle": " · ".join([part for part in subtitle_parts if part]),
                    "snippet": (pro.message or "")[:180],
                }
            )
    except Exception as exc:
        current_app.logger.warning("Search professionals skipped: %s", exc)
        results["professionals"] = [
            {
                "title": f"Voir les professionnels pour '{q}'",
                "url": url_for("main.professionnels", q=q),
                "subtitle": "Professionnels",
                "snippet": "Ouvrir la liste et filtrer.",
            }
        ]

    results["requests"] = finalize(results["requests"])
    results["categories"] = finalize(results["categories"])
    results["professionals"] = finalize(results["professionals"])

    return render_template("search_results.html", q=q, results=results), 200


@main_bp.route("/categories", methods=["GET"])
@limiter.limit("120 per minute")
def categories():
    """Legacy alias for orienter."""
    return redirect(url_for("main.orienter"), code=301)


@main_bp.route("/orienter", methods=["GET"])
@limiter.limit("120 per minute")
def orienter():
    return render_template("orienter.html")


@main_bp.route("/achievements", methods=["GET"])
def achievements():
    if not session.get("volunteer_logged_in"):
        return redirect(url_for("main.become_volunteer"))

    achievements_data = [
        {"title": "First login", "points": 10, "status": "unlocked"},
        {"title": "First request handled", "points": 20, "status": "locked"},
    ]
    return render_template("achievements.html", achievements=achievements_data), 200


@main_bp.route("/volunteer_login", methods=["GET", "POST"])
@limiter.limit("5 per 5 minutes")
@limiter.limit("20 per hour")
@limiter.limit("3 per hour", key_func=email_or_ip_key, methods=["POST"])
def volunteer_login():
    # Legacy entrypoint: keep dev bypass support, but route real users to magic-link flow.
    if not current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED"):
        current_app.logger.warning("[VOL-LOGIN] blocked (non-dev) ip=%s", _client_ip())
        return redirect(
            url_for("main.become_volunteer", next=url_for("main.volunteer_profile")),
            code=303,
        )

    current_app.logger.info(
        "volunteer_login cfg bypass_enabled=%s bypass_email=%s args_dev=%s",
        current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED"),
        current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL"),
        request.args.get("dev"),
    )
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        generic_msg = _("If the email is valid, you will receive a login link.")

        log_security_event(
            "magic_link_requested", actor_type="anonymous", meta={"flow": "volunteer"}
        )

        if current_app.config.get(
            "VOLUNTEER_DEV_BYPASS_ENABLED"
        ) and email == current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL"):
            v = Volunteer.query.filter_by(email=email).first()
            if not v:
                v = Volunteer(email=email, is_active=True)
                db.session.add(v)
                db.session.commit()

            session.clear()
            session["volunteer_id"] = v.id
            session["volunteer_logged_in"] = True
            log_security_event(
                "volunteer_dev_bypass_login", actor_type="volunteer", actor_id=v.id
            )
            target = get_safe_next(url_for("main.volunteer_dashboard"))
            return redirect(target, code=303)

        if not email:
            flash(generic_msg, "info")
            return render_template("volunteer_login.html", minimal_page=True), 200
        # Dev-only route: if bypass email is not used, keep anti-enumeration UX.
        flash(generic_msg, "info")
        return render_template("volunteer_login.html", minimal_page=True), 200

    prefill_email = ""
    if (
        current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED")
        and request.args.get("dev") == "1"
    ):
        prefill_email = current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL") or ""

    return (
        render_template(
            "volunteer_login.html", minimal_page=True, prefill_email=prefill_email
        ),
        200,
    )


@main_bp.post("/volunteer/logout")
def volunteer_logout():
    session.pop("volunteer_id", None)
    session.pop("just_logged_in", None)
    session.pop("demo_pending", None)
    return redirect(url_for("main.index"), code=303)


@main_bp.route("/become_volunteer", methods=["GET", "POST"])
def become_volunteer():
    """Public landing + submission endpoint for new volunteers."""
    if request.method == "GET":
        safe_next = _safe_volunteer_next_path(request.args.get("next"))
        if safe_next:
            session["volunteer_next"] = safe_next
        else:
            session.pop("volunteer_next", None)
        flow_mode = "login" if safe_next else "register"
        return render_template("become_volunteer.html", flow_mode=flow_mode), 200

    if request.method == "POST":
        default_cooldown_seconds = 14
        response_cooldown_seconds = default_cooldown_seconds
        accept = (request.headers.get("Accept") or "").lower()
        wants_json = "application/json" in accept

        def _volunteer_magic_ok_response(resend_email: str = ""):
            if wants_json:
                return (
                    jsonify(
                        {"ok": True, "cooldown_seconds": int(response_cooldown_seconds)}
                    ),
                    200,
                )
            safe_email = (
                (resend_email or session.get("volunteer_magic_email") or "")
                .strip()
                .lower()
            )
            return (
                render_template(
                    "volunteer_link_sent.html",
                    resend_email=safe_email,
                    cooldown_seconds=int(response_cooldown_seconds),
                ),
                200,
            )

        # Server-side anti-bot (frontend can be bypassed)
        suppress = False
        suppress_reasons: list[str] = []
        website = (
            request.form.get("company_fax") or request.form.get("website") or ""
        ).strip()
        started_at = (request.form.get("started_at") or "").strip()
        if website:
            # Browser autofill can populate hidden honeypot fields with the user's email.
            # Treat obvious autofill patterns as non-bot to avoid false suppressions.
            website_l = website.lower()
            email_l = (request.form.get("email") or "").strip().lower()
            if "@" in website_l or (email_l and website_l == email_l):
                current_app.logger.info(
                    "[VOL-MAGIC] honeypot autofill ignored website=%r email=%r",
                    website,
                    email_l,
                )
            else:
                suppress = True
                suppress_reasons.append("honeypot")
        try:
            started_ms = int(started_at)
        except Exception:
            started_ms = 0
        # Keep this threshold low to avoid suppressing legitimate autofill + click flows.
        if started_ms and (int(time.time() * 1000) - started_ms) < 900:
            suppress = True
            suppress_reasons.append("timing")

        # Server-side rate-limit (MVP): same UX either way (anti-enumeration).
        ip = _client_ip()
        form_email = (request.form.get("email") or "").strip().lower()
        session_email = (session.get("volunteer_magic_email") or "").strip().lower()
        # For JSON resend requests, allow fallback to session email.
        # For regular form submits, require explicit form email to avoid stale session sends.
        email = form_email or (session_email if wants_json else "")
        email_key = email or ip
        ip_allowed, _ip_retry_after = _rate_limit_check(
            f"ml:vol:ip:{ip}", limit=10, window_sec=600
        )
        if not ip_allowed:
            suppress = True
            suppress_reasons.append("ip-limit")
        email_allowed, _email_retry_after = _rate_limit_check(
            f"ml:vol:email:{email_key}", limit=3, window_sec=600
        )
        if not email_allowed:
            suppress = True
            suppress_reasons.append("email-limit")

        # Volunteer magic link (purpose="volunteer") — always return generic OK.
        if not email or "@" not in email:
            return _volunteer_magic_ok_response()
        session["volunteer_magic_email"] = email

        # UX cooldown: 1 send per email_key per default_cooldown_seconds.
        cooldown_allowed, cooldown_retry_after = _rate_limit_check(
            f"ml:vol:cooldown:{email_key}",
            limit=1,
            window_sec=default_cooldown_seconds,
        )
        if not cooldown_allowed:
            suppress = True
            suppress_reasons.append("cooldown")
            response_cooldown_seconds = int(max(1, cooldown_retry_after))

        current_app.logger.info(
            "[VOL-MAGIC] pre-send decision suppress=%s reasons=%s email=%s ip=%s",
            suppress,
            suppress_reasons,
            email,
            ip,
        )
        if suppress:
            current_app.logger.info(
                "[VOL-MAGIC] suppress=%s reason=%s website=%s started_at=%s ip=%s email_key=%s cooldown_seconds=%s",
                suppress,
                ",".join(suppress_reasons) if suppress_reasons else "-",
                bool(website),
                started_at,
                ip,
                email_key,
                response_cooldown_seconds,
            )
            return _volunteer_magic_ok_response(resend_email=email)
        current_app.logger.info(
            "[VOL-MAGIC] not suppressed, continuing to token+send email=%s", email
        )

        try:
            current_app.logger.info("[VOL-MAGIC] creating token for email=%s", email)
            raw_token = secrets.token_urlsafe(32)
            token_hash = _sha256_hex(raw_token)
            ttl_minutes = 15
            expires_at = utc_now() + timedelta(minutes=ttl_minutes)

            row = MagicLinkToken(
                purpose="volunteer",
                email=email,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            db.session.add(row)
            db.session.commit()
            current_app.logger.info(
                "[MAGIC LINK VOL] token created id=%s email=%s expires_at=%s",
                row.id,
                email,
                expires_at,
            )

            base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
            path = url_for("main.magic_link_consume", token=raw_token, _external=False)
            magic_url = (
                f"{base}{path}"
                if base
                else url_for("main.magic_link_consume", token=raw_token, _external=True)
            )

            # Keep volunteer login subject stable in FR regardless of request locale.
            subject = "Votre lien de connexion HelpChain (15 min)"
            context = {
                "magic_link_url": magic_url,
                "ttl_minutes": ttl_minutes,
                "intro_text": _(
                    "Sans mot de passe. Recevez un lien sécurisé par e-mail."
                ),
                "button_text": _("Ouvrir mon lien de connexion"),
                "fallback_text": _(
                    "Si le bouton ne fonctionne pas, copiez-collez ce lien :"
                ),
                "privacy_line": _("Données minimales, respect RGPD"),
                "ignore_line": _(
                    "Si vous n’êtes pas à l’origine de cette demande, ignorez cet e-mail."
                ),
            }

            try:
                from backend.mail_service import send_notification_email

                current_app.logger.info(
                    "[VOL-MAGIC] about to call send_notification_email email=%s", email
                )
                current_app.logger.info("[VOL-MAGIC] sending to=%s", email)
                send_ok = send_notification_email(
                    email,
                    subject,
                    "emails/magic_link.html",
                    context,
                    purpose="volunteer_magic_link",
                )
                current_app.logger.info(
                    "[MAGIC LINK VOL] token_id=%s email_send_ok=%s",
                    row.id,
                    send_ok,
                )
            except Exception as e:
                current_app.logger.warning(
                    "[EMAIL] volunteer magic link send failed token_id=%s: %s",
                    row.id,
                    e,
                )
        except OperationalError:
            # Table missing / not migrated yet: keep anti-enumeration behavior.
            db.session.rollback()
            current_app.logger.exception(
                "[VOL-MAGIC] operational error while creating/sending magic link"
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "[VOL-MAGIC] unexpected error while creating/sending magic link"
            )

        # Keep UX consistent and privacy-safe.
        return _volunteer_magic_ok_response(resend_email=email)

    return render_template("become_volunteer.html"), 200


@main_bp.get("/volunteer/confirmation")
def volunteer_confirmation():
    """Confirmation screen after submitting volunteer interest."""
    return render_template("volunteer_confirmation.html"), 200


@main_bp.get("/volunteer/onboarding")
@require_volunteer_login
def volunteer_onboarding():
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))
    if getattr(volunteer, "volunteer_onboarded", False):
        return redirect(get_safe_next(url_for("main.volunteer_dashboard")))
    return render_template("volunteer_onboarding.html"), 200


@main_bp.post("/volunteer/onboarding")
@require_volunteer_login
def volunteer_onboarding_submit():
    volunteer_id = session.get("volunteer_id")
    if not volunteer_id:
        return redirect(url_for("main.become_volunteer", next=request.path))

    volunteer = Volunteer.query.get(volunteer_id)
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    # ✅ V2.1.a — mark onboarding complete
    volunteer.volunteer_onboarded = True
    db.session.commit()

    flash(
        _("You're all set! You can now see requests where your help matters."),
        "success",
    )

    return redirect(url_for("main.volunteer_dashboard"))


@main_bp.get("/volunteer/dashboard")
@require_volunteer_login
def volunteer_dashboard():
    volunteer = _current_volunteer()

    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))
    if not getattr(volunteer, "volunteer_onboarded", False):
        return redirect(
            url_for("main.volunteer_onboarding", next=request.path), code=303
        )

    just_logged_in = session.pop("just_logged_in", None)

    open_requests = scoped_requests_query().filter_by(status="open").all()

    my_interest_req_ids = set(
        rid
        for (rid,) in db.session.query(VolunteerInterest.request_id)
        .filter(VolunteerInterest.volunteer_id == volunteer.id)
        .all()
    )

    # Show matches even if the volunteer already expressed interest.
    # The dashboard will reflect interest status via badges/CTAs.
    matched_requests = [
        r
        for r in open_requests
        if is_request_matching_volunteer(r, volunteer, interested_request_ids=None)
    ]
    # Smart matching controls
    min_match_raw = (request.args.get("min") or "55").strip()
    try:
        min_match_int = int(min_match_raw)
    except Exception:
        min_match_int = 55
    if min_match_int not in (40, 50, 55, 60, 65, 70, 75, 80):
        min_match_int = 55
    match_prio = (request.args.get("prio") or "all").strip().lower()
    if match_prio not in {"all", "urgent", "high"}:
        match_prio = "all"
    match_near = (request.args.get("near") or "").strip() == "1"
    near_km = 25
    has_coords = bool(
        getattr(volunteer, "latitude", None) is not None
        and getattr(volunteer, "longitude", None) is not None
    )
    if match_near and not has_coords:
        match_near = False

    # Smart matching layers:
    # - strong matches: >=55%
    # - low-confidence matches: 40..54%
    all_scored_raw = get_matched_requests_v1(
        volunteer,
        limit=200,
        min_percent=0,
        prio=match_prio,
        near=match_near,
        max_text_chars=800,
        cache_ttl_sec=90,
    )
    strong_raw = [t for t in all_scored_raw if int(round(t[1])) >= 55]
    low_conf_raw = [t for t in all_scored_raw if 40 <= int(round(t[1])) < 55]
    strong_raw = [t for t in strong_raw if int(round(t[1])) >= min_match_int]
    matched_v1_raw = strong_raw[:8]
    matched_v1 = []
    for req, pct, breakdown in matched_v1_raw:
        matched_v1.append(
            {"req": req, "pct": int(round(pct)), "breakdown": dict(breakdown or {})}
        )
    low_conf_count = len(low_conf_raw)

    # Dynamic guidance + profile completeness
    skills_raw = (getattr(volunteer, "skills", None) or "").strip()
    skills_items = [s.strip() for s in skills_raw.split(",") if s.strip()]
    skills_count = len(skills_items)
    has_location = bool((getattr(volunteer, "location", None) or "").strip())
    has_availability = bool((getattr(volunteer, "availability", None) or "").strip())
    has_coords = (
        getattr(volunteer, "latitude", None) is not None
        and getattr(volunteer, "longitude", None) is not None
    )
    has_skill_depth = skills_count >= 2
    checks = [has_location, has_skill_depth, has_availability, has_coords]
    profile_completeness = int(round((sum(1 for x in checks if x) / len(checks)) * 100))

    smart_tips = []
    if not has_location:
        smart_tips.append(
            {
                "icon": "",
                "text": "Enable location to unlock distance scoring (+20%).",
            }
        )
    if not has_skill_depth:
        smart_tips.append(
            {
                "icon": "",
                "text": "Add 2-3 specific skills to increase match score (+45%).",
            }
        )
    if not has_coords:
        smart_tips.append(
            {
                "icon": "",
                "text": "Distance matching is currently disabled (missing coordinates).",
            }
        )
    if not has_availability:
        smart_tips.append(
            {
                "icon": "",
                "text": "Add availability so requests can be prioritized for your schedule.",
            }
        )

    pending_ids = set(
        rid
        for (rid,) in db.session.query(VolunteerInterest.request_id)
        .filter(
            VolunteerInterest.volunteer_id == volunteer.id,
            VolunteerInterest.status == "pending",
        )
        .all()
    )

    # --- Interest status map (for dashboard badges/CTAs)
    req_ids = [r.id for r in matched_requests] if matched_requests else []
    interest_by_req_id = {}
    if req_ids:
        interests = (
            VolunteerInterest.query.filter(
                VolunteerInterest.volunteer_id == volunteer.id,
                VolunteerInterest.request_id.in_(req_ids),
            )
            .order_by(VolunteerInterest.id.asc())
            .all()
        )
        # If duplicates exist, keep the most recent one
        for it in interests:
            interest_by_req_id[it.request_id] = (it.status or "").upper()

    # --- My interests (dashboard lists) ---
    my_interests = (
        db.session.query(VolunteerInterest, Request)
        .join(Request, Request.id == VolunteerInterest.request_id)
        .filter(Request.structure_id == _current_structure_id())
        .filter(VolunteerInterest.volunteer_id == volunteer.id)
        .order_by(VolunteerInterest.created_at.desc())
        .limit(30)
        .all()
    )

    my_pending: list[dict] = []
    my_approved: list[dict] = []
    my_rejected: list[dict] = []
    my_first_approved_req = None
    my_first_closed_req = None

    for vi, req in my_interests:
        row = {"vi": vi, "req": req}
        status_norm = (vi.status or "").lower()
        my_interest_req_ids.add(req.id)
        if status_norm == "pending":
            my_pending.append(row)
        elif status_norm == "approved":
            my_approved.append(row)
            if not my_first_approved_req:
                my_first_approved_req = row
        elif status_norm == "rejected":
            my_rejected.append(row)
        else:
            my_pending.append(row)  # fallback bucket
        try:
            req_status = normalize_request_status(getattr(req, "status", None))
        except Exception:
            req_status = (getattr(req, "status", None) or "").lower()
        if not my_first_closed_req and req_status in {
            "closed",
            "done",
            "completed",
            "resolved",
        }:
            my_first_closed_req = row

    # --- Generate match notifications lazily (MVP) ---
    profile_complete = bool(volunteer.location) and bool(volunteer.availability)
    if volunteer.is_active and profile_complete:
        eligible_matches = [
            r for r in matched_requests if r.id not in my_interest_req_ids
        ]
        ensure_new_match_notifications(
            volunteer_id=volunteer.id, request_rows=eligible_matches
        )

    current_app.logger.info(
        "Matching check",
        extra={
            "volunteer_id": volunteer.id,
            "matched_requests": len(matched_requests),
        },
    )

    actions = (
        db.session.query(VolunteerAction.request_id, VolunteerAction.action)
        .filter(VolunteerAction.volunteer_id == volunteer.id)
        .all()
    )
    my_actions_by_req_id = {rid: act for rid, act in actions}

    unread_match_notifications = (
        Notification.query.filter_by(
            volunteer_id=volunteer.id, is_read=False, type="new_match"
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    unread_count = Notification.query.filter_by(
        volunteer_id=volunteer.id, is_read=False
    ).count()
    match_count = int(len(unread_match_notifications or []))

    # --- In-app notifications (V2.2.A) ---
    locale_code = str(babel_get_locale())[:2]
    notif_copy = {
        "fr": {
            "new_match": {
                "title": "New request matches your profile",
                "body": "Localisation + compétences + disponibilité sont alignées. Consultez et choisissez si vous voulez aider.",
                "cta": "Voir la demande",
            },
            "help_accepted": {
                "title": "Vous êtes connectés. Vous pouvez aider.",
                "body": "La personne a accepté votre aide. Vous pouvez maintenant coordonner.",
                "cta": "Ouvrir la demande",
            },
            "request_done": {
                "title": "Cette demande est terminée. Merci.",
                "body": "Aidez une autre personne quand vous le souhaitez.",
                "cta": "Voir les demandes",
            },
        },
        "bg": {
            "new_match": {
                "title": "Нова заявка съвпада с профила ти",
                "body": "Локация + умения + наличност съвпадат. Виж детайлите и реши дали да помогнеш.",
                "cta": "Виж заявката",
            },
            "help_accepted": {
                "title": "Свързани сте. Можеш да помогнеш вече.",
                "body": "Заявителят прие помощта ти. Сега може да координирате.",
                "cta": "Отвори заявката",
            },
            "request_done": {
                "title": "Тази заявка е приключена. Благодарим.",
                "body": "Можеш да помогнеш на друг човек, когато решиш.",
                "cta": "Виж заявки",
            },
        },
        "en": {
            "new_match": {
                "title": "New request matches your profile",
                "body": "Location + skills + availability align. Review it and choose if you want to help.",
                "cta": "View request",
            },
            "help_accepted": {
                "title": "You’re connected. You can now help.",
                "body": "The requester accepted your help. Coordinate when ready.",
                "cta": "Open request",
            },
            "request_done": {
                "title": "This request is now completed. Thank you.",
                "body": "Help someone else whenever you like.",
                "cta": "View requests",
            },
        },
    }
    notif_lang = notif_copy.get(locale_code, notif_copy["en"])
    notifications: list[dict] = []
    badge_count = 0

    if my_first_approved_req:
        notifications.append(
            {
                "kind": "help_accepted",
                "title": notif_lang["help_accepted"]["title"],
                "body": notif_lang["help_accepted"]["body"],
                "cta_label": notif_lang["help_accepted"]["cta"],
                "cta_href": url_for(
                    "main.volunteer_request_details",
                    req_id=my_first_approved_req["req"].id,
                ),
                "tone": "success",
            }
        )
        badge_count = 0  # badge clears automatically
    elif my_first_closed_req:
        notifications.append(
            {
                "kind": "request_done",
                "title": notif_lang["request_done"]["title"],
                "body": notif_lang["request_done"]["body"],
                "cta_label": notif_lang["request_done"]["cta"],
                "cta_href": url_for("main.volunteer_dashboard") + "#hc-matches",
                "tone": "secondary",
            }
        )
        badge_count = 0
    elif unread_match_notifications:
        unread_match_count = len(unread_match_notifications)
        first_match = unread_match_notifications[0]
        if locale_code == "bg":
            title = (
                f"Имаш съвпадение с {unread_match_count} заявка"
                if unread_match_count == 1
                else f"Имаш съвпадение с {unread_match_count} заявки"
            )
            body = "Отвори и избери следващо действие."
            cta = "Виж"
        elif locale_code == "fr":
            title = (
                "Vous avez une demande correspondante"
                if unread_match_count == 1
                else f"Vous avez {unread_match_count} demandes correspondantes"
            )
            body = "Ouvrez et choisissez la prochaine action."
            cta = "Voir"
        else:
            title = (
                "You've been matched to 1 request"
                if unread_match_count == 1
                else f"You've been matched to {unread_match_count} requests"
            )
            body = "Open and choose your next action."
            cta = "View"
        notifications.append(
            {
                "kind": "new_match",
                "title": title,
                "body": body,
                "cta_label": cta,
                "cta_href": url_for(
                    "main.volunteer_request_details", req_id=first_match.request_id
                ),
                "tone": "primary",
            }
        )
        badge_count = 1

    return (
        render_template(
            "volunteer_dashboard.html",
            volunteer=volunteer,
            matches=matched_requests,
            matched_v1=matched_v1,
            match_min=min_match_int,
            match_prio=match_prio,
            match_near=match_near,
            near_km=near_km,
            has_coords=has_coords,
            low_conf_count=low_conf_count,
            profile_completeness=profile_completeness,
            smart_tips=smart_tips,
            just_logged_in=bool(just_logged_in),
            pending_ids=pending_ids,
            interest_by_req_id=interest_by_req_id,
            my_pending=my_pending,
            my_approved=my_approved,
            my_rejected=my_rejected,
            notifications=notifications,
            match_count=int(match_count or 0),
            volunteer_badge_count=badge_count,
            unread_count=unread_count,
            my_actions_by_req_id=my_actions_by_req_id,
        ),
        200,
    )


@main_bp.post("/volunteer/match/<int:req_id>/seen")
@main_bp.post("/volunteer/requests/<int:req_id>/seen")
@require_volunteer_login
def volunteer_request_seen(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return jsonify({"ok": False}), 401
    try:
        match_mark_seen(volunteer.id, req_id)
        return jsonify({"ok": True}), 200
    except Exception:
        current_app.logger.exception("Failed to mark seen req_id=%s", req_id)
        db.session.rollback()
        return jsonify({"ok": False}), 500


@main_bp.post("/volunteer/match/<int:req_id>/dismiss")
@main_bp.post("/volunteer/requests/<int:req_id>/dismiss")
@require_volunteer_login
def volunteer_request_dismiss(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return jsonify({"ok": False}), 401
    try:
        match_dismiss_for(volunteer.id, req_id, hours=48)
        return jsonify({"ok": True, "dismiss_hours": 48}), 200
    except Exception:
        current_app.logger.exception("Failed to dismiss req_id=%s", req_id)
        db.session.rollback()
        return jsonify({"ok": False}), 500


@main_bp.get("/volunteer/requests/<int:req_id>")
@require_volunteer_login
def volunteer_request_details(req_id: int):
    """Детайли за заявка, достъпни за логнат доброволец."""
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    req = get_scoped_request_or_404(req_id)
    try:
        db.session.refresh(req)
    except Exception:
        pass

    if not can_view_request(volunteer, req, db):
        abort(404)

    vi = (
        VolunteerInterest.query.filter_by(volunteer_id=volunteer.id, request_id=req.id)
        .order_by(VolunteerInterest.id.desc())
        .first()
    )

    already_pending = bool(vi and vi.status == "pending")
    already_approved = bool(vi and vi.status == "approved")
    already_rejected = bool(vi and vi.status == "rejected")
    try:
        status_norm = normalize_request_status(getattr(req, "status", None))
    except Exception:
        status_norm = getattr(req, "status", None)

    action_row = VolunteerAction.query.filter_by(
        request_id=req.id, volunteer_id=volunteer.id
    ).one_or_none()
    # Keep a single "last signal" object for the template (CAN_HELP / CANT_HELP).
    # This is effectively 1 row due to uq_volunteer_action_request_volunteer.
    my_last_signal = (
        VolunteerAction.query.filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .order_by(
            VolunteerAction.updated_at.desc(),
            VolunteerAction.created_at.desc(),
            VolunteerAction.id.desc(),
        )
        .first()
    )

    # опционален контрол: показваме само ако е match/отворена
    # if not is_request_matching_volunteer(req, volunteer):
    #     abort(403)

    # Mark related match notification as read (if any)
    try:
        notif_changed = (
            Notification.query.filter_by(
                volunteer_id=volunteer.id,
                request_id=req.id,
                type="new_match",
                is_read=False,
            ).update({"is_read": True, "read_at": datetime.utcnow()})
            > 0
        )
        state_changed = mark_request_seen_for_volunteer(
            request_id=req.id,
            volunteer_id=volunteer.id,
            seen_at=utc_now(),
            commit=False,
        )
        if notif_changed or state_changed:
            db.session.commit()
    except Exception:
        db.session.rollback()

    return (
        render_template(
            "volunteer_request_details.html",
            req=req,
            volunteer=volunteer,
            status_norm=status_norm,
            is_pending=already_pending,
            already_pending=already_pending,
            already_approved=already_approved,
            already_rejected=already_rejected,
            is_demo=False,
            volunteer_action=action_row,
            my_last_signal=my_last_signal,
            my_signal=my_last_signal,  # alias for template clarity/back-compat
        ),
        200,
    )


@main_bp.get("/volunteer/requests/demo")
@require_volunteer_login
def volunteer_request_demo():
    """Demo детайли за примера в таблото."""
    volunteer = _current_volunteer()
    already_pending = bool(session.get("demo_pending"))
    demo_req = SimpleNamespace(
        id="demo",
        title="Примерна заявка",
        city="Paris",
        created_at="току-що",
        description="Човек търси помощ за документи и насоки къде да ги подаде.",
    )
    return (
        render_template(
            "volunteer_request_details.html",
            req=demo_req,
            volunteer=volunteer,
            is_pending=already_pending,
            already_pending=already_pending,
            already_approved=False,
            already_rejected=False,
            is_demo=True,
        ),
        200,
    )


@main_bp.post("/volunteer/requests/<int:req_id>/help")
@require_volunteer_login
def volunteer_help(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    current_app.logger.info("VOL_HELP DB=%s", db.engine.url)
    current_app.logger.info("VOL_HELP req_id=%s", req_id)

    req = get_scoped_request_or_404(req_id)

    interest = VolunteerInterest.query.filter_by(
        volunteer_id=volunteer.id, request_id=req.id
    ).one_or_none()

    if interest is None:
        interest = VolunteerInterest(
            volunteer_id=volunteer.id,
            request_id=req.id,
            status="pending",
        )
        db.session.add(interest)
    else:
        interest.status = "pending"

    current_app.logger.info(
        "VOL_HELP about to commit volunteer_id=%s request_id=%s", volunteer.id, req.id
    )
    db.session.commit()
    current_app.logger.info(
        "VOL_HELP committed interest_id=%s status=%s", interest.id, interest.status
    )

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "status": interest.status})

    # Clear match notification when volunteer expresses interest
    try:
        Notification.query.filter_by(
            volunteer_id=volunteer.id, request_id=req.id, type="new_match"
        ).update({"is_read": True, "read_at": datetime.utcnow()})
        db.session.commit()
    except Exception:
        db.session.rollback()

    flash(_("Got it. Your signal was sent to the team."), "success")
    return redirect(url_for("main.volunteer_request_details", req_id=req_id), code=303)


def _upsert_volunteer_action(req_obj, volunteer, action_value: str):
    """Create or update a volunteer action signal for a request."""
    row = VolunteerAction.query.filter_by(
        request_id=req_obj.id, volunteer_id=volunteer.id
    ).one_or_none()
    old_action = getattr(row, "action", None) if row else None
    if row is None:
        row = VolunteerAction(
            request_id=req_obj.id,
            volunteer_id=volunteer.id,
            action=action_value,
        )
        db.session.add(row)
    else:
        row.action = action_value
    db.session.add(
        RequestActivity(
            request_id=req_obj.id,
            volunteer_id=volunteer.id,
            action=f"volunteer_{action_value.lower()}",
            old_value=old_action,
            new_value=action_value,
        )
    )
    db.session.commit()
    _emit_event(
        "volunteer_action_signal",
        {
            "volunteer_id": volunteer.id,
            "request_id": req_obj.id,
            "action": action_value,
        },
    )
    return row


@main_bp.post("/volunteer/requests/<int:req_id>/can-help")
@require_volunteer_login
def volunteer_can_help(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    req = get_scoped_request_or_404(req_id)

    _upsert_volunteer_action(req, volunteer, "CAN_HELP")

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "action": "CAN_HELP"})
    flash(_("Got it. Your signal was sent to the team."), "success")
    return redirect(url_for("main.volunteer_request_details", req_id=req_id), code=303)


@main_bp.post("/volunteer/requests/<int:req_id>/cant-help")
@require_volunteer_login
def volunteer_cant_help(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    req = get_scoped_request_or_404(req_id)

    _upsert_volunteer_action(req, volunteer, "CANT_HELP")

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "action": "CANT_HELP"})
    flash(_("Got it. Your signal was sent to the team."), "success")
    return redirect(url_for("main.volunteer_request_details", req_id=req_id), code=303)


@main_bp.post("/volunteer/requests/demo/help")
@require_volunteer_login
def volunteer_request_help_demo():
    """Demo: не записваме нищо, само връщаме UX feedback."""
    session["demo_pending"] = True
    flash("Благодарим! Интересът ти е отбелязан (демо).", "success")
    return redirect(url_for("main.volunteer_request_demo"))


@main_bp.get("/volunteer/notifications")
@require_volunteer_login
def volunteer_notifications():
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    # Volunteer UI: notifications are primarily keyed by `volunteer_id`.
    owner_col = getattr(Notification, "volunteer_id", None) or getattr(
        Notification, "user_id", None
    )
    if owner_col is None:
        abort(500)
    notifs = (
        Notification.query.filter(owner_col == volunteer.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = Notification.query.filter(
        owner_col == volunteer.id,
        Notification.is_read == False,  # noqa: E712
    ).count()

    return (
        render_template(
            "volunteer_notifications.html",
            notifications=notifs,
            unread_count=unread_count,
        ),
        200,
    )


@main_bp.post("/volunteer/notifications/<int:notif_id>/open")
@require_volunteer_login
def volunteer_notification_open(notif_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    try:
        target_url, request_id = mark_notification_opened(notif_id, volunteer.id)
    except LookupError:
        abort(404)
    except RuntimeError:
        abort(500)

    _emit_event(
        "volunteer_notification_open",
        {
            "volunteer_id": volunteer.id,
            "notification_id": notif_id,
            "request_id": request_id,
        },
    )
    return redirect(target_url)


@main_bp.route("/volunteer/profile", methods=["GET", "POST"])
@require_volunteer_login
def volunteer_profile():
    volunteer = _current_volunteer()

    if not volunteer:
        return redirect(url_for("main.become_volunteer", next=request.path))

    if request.method == "POST":
        current_app.logger.info(
            "VOL PROFILE SAVE location=%s", request.form.get("location")
        )
        for field in (
            "name",
            "email",
            "phone",
            "location",
            "city",
            "skills",
            "notes",
            "availability",
        ):
            if field in request.form:
                setattr(volunteer, field, request.form.get(field, "").strip())
        db.session.commit()
        return redirect(url_for("main.volunteer_dashboard"))

    return render_template("volunteer_profile.html", volunteer=volunteer), 200


@main_bp.get("/request")
@limiter.limit("30 per minute")
def request_category():
    slug = request.args.get("category")
    canonical = ALIASES.get(slug, slug) if slug else None
    category = CATEGORIES.get(canonical) if canonical else None

    if not slug:
        return (
            render_template(
                "request_category.html",
                category=None,
                COMMON=COMMON,
                categories=CATEGORIES,
                not_found=False,
                requested_slug=None,
            ),
            200,
        )

    if not category:
        return (
            render_template(
                "request_category.html",
                category=None,
                COMMON=COMMON,
                categories=CATEGORIES,
                not_found=True,
                requested_slug=slug,
            ),
            404,
        )

    show_emergency = category["ui"].get("severity") == "critical"
    return (
        render_template(
            "request_category.html",
            category=category,
            COMMON=COMMON,
            show_emergency=show_emergency,
            emergency_number=COMMON.get("emergency_number"),
            requested_slug=slug,
        ),
        200,
    )


@main_bp.get("/request/form")
def request_form():
    slug = request.args.get("category")
    canonical = ALIASES.get(slug, slug) if slug else None
    category = CATEGORIES.get(canonical) if canonical else None

    if not slug:
        return redirect(url_for("main.request_category"))

    if not category:
        current_app.logger.warning("Invalid category slug for form: %s", slug)
        return redirect(url_for("main.request_category", category=slug))

    return render_template("request_form.html", category=category, COMMON=COMMON)


@main_bp.get("/chat")
def chat_page():
    return render_template("chat/chat.html"), 200


@main_bp.route("/about")
def about():
    return render_template("about.html")


@main_bp.get("/gouvernance")
def gouvernance():
    # Temporary alias to avoid 500 if templates or old links reference it.
    return redirect(url_for("main.about"), code=302)


def normalize_request_form(form):
    """
    Canonical mapping from HTML form fields -> backend variables.

    Accepts:
      - category OR type (optional)
      - urgency OR priority (optional)
      - description OR problem OR message (your HTML uses "problem")
    """
    category = (form.get("category") or form.get("type") or "").strip().lower()
    urgency = (form.get("urgency") or form.get("priority") or "").strip().lower()
    description = (
        form.get("description") or form.get("problem") or form.get("message") or ""
    ).strip()
    return category, urgency, description


def validate_submit_request_form(form):
    """Manual submit_request validator returning (errors, cleaned_values)."""
    errors: dict[str, str] = {}

    category, urgency, description = normalize_request_form(form)
    name = (form.get("name") or "").strip()
    phone = (form.get("phone") or "").strip()
    email = (form.get("email") or "").strip()
    location_text = (form.get("location_text") or form.get("location") or "").strip()
    title = (form.get("title") or "").strip()
    consent = (form.get("privacy_consent") or "").strip()

    MAX_NAME_LEN = 80
    MAX_TITLE_LEN = 120
    MAX_DESC_LEN = 2000
    MAX_LOCATION_LEN = 120
    MAX_PHONE_LEN = 32
    MAX_EMAIL_LEN = 254

    if consent != "1":
        errors["privacy_consent"] = _(
            "Veuillez accepter la Politique de confidentialité (RGPD) pour continuer."
        )

    for label, value, max_len in (
        ("name", name, MAX_NAME_LEN),
        ("title", title, MAX_TITLE_LEN),
        ("description", description, MAX_DESC_LEN),
        ("location_text", location_text, MAX_LOCATION_LEN),
        ("phone", phone, MAX_PHONE_LEN),
        ("email", email, MAX_EMAIL_LEN),
    ):
        if len(value) > max_len:
            if label == "description":
                errors[label] = _("Please shorten the text.")
            else:
                errors[label] = _("Please shorten the %(field)s.", field=label)

    for label, value in (
        ("name", name),
        ("title", title),
        ("description", description),
        ("location_text", location_text),
    ):
        if has_control_chars(value):
            errors[label] = _("Invalid characters detected.")

    if len(name) < 2:
        errors["name"] = _("Моля, въведете име (поне 2 символа).")

    if len(description) < 10:
        errors["description"] = _("Моля, опишете проблема (поне 10 символа).")

    if not phone and not email:
        msg = _("Моля, въведете поне телефон или имейл.")
        errors["phone"] = msg
        errors["email"] = msg

    allowed_categories = {"medical", "social", "tech", "admin", "other", "general", ""}
    if category not in allowed_categories:
        errors["category"] = _("Please select a valid category.")

    allowed_urgency = {"low", "normal", "medium", "urgent", "critical", "emergency", ""}
    if urgency not in allowed_urgency:
        errors["urgency"] = _("Please select a valid urgency.")

    # urgency -> priority (DB expects low/medium/high)
    priority_map = {
        "low": "low",
        "medium": "medium",
        "normal": "medium",
        "urgent": "high",
        "critical": "high",
        "emergency": "high",
    }
    priority = priority_map.get(urgency, "medium")

    cleaned = {
        "name": name,
        "phone": phone,
        "email": email,
        "category": category or "general",
        "urgency": urgency or "normal",
        "priority": priority,
        "title": title,
        "description": description,
        "location_text": location_text,
        "started_at": (form.get("started_at") or "").strip(),
    }
    return errors, cleaned


@main_bp.route("/submit_request", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
@limiter.limit("10 per hour", methods=["POST"])
def submit_request():
    """Подаване на заявка за помощ"""
    trust_items = [
        ("&#10003;", "fas fa-shield-heart", _("Verified volunteers only")),
        ("&#9733;", "fas fa-user-clock", _("Fast matching - no bureaucracy")),
        ("&#9889;", "fas fa-lock", _("We keep your data private")),
    ]

    if request.method == "POST":
        current_app.logger.warning("SUBMIT_REQUEST POST hit")
        current_app.logger.warning("Form keys=%s", list(request.form.keys()))
        current_app.logger.warning(
            "website(honeypot)='%s'", (request.form.get("website") or "").strip()
        )
        # Honeypot anti-bot field (ако се задейства, искам да го ВИДИШ)
        website = (request.form.get("website") or "").strip()
        if website:
            current_app.logger.warning(
                "Honeypot triggered on submit_request: website=%r", website
            )
            # Pretend success to avoid bot feedback loops
            return (
                render_template(
                    "submit_request.html", trust_items=trust_items, success=True
                ),
                200,
            )

        errors, cleaned = validate_submit_request_form(request.form)

        current_app.logger.warning(
            "Parsed: name=%r(len=%s) phone=%r(len=%s) email=%r(len=%s) category=%r urgency=%r desc_len=%s title=%r",
            cleaned["name"],
            len(cleaned["name"] or ""),
            cleaned["phone"],
            len(cleaned["phone"] or ""),
            cleaned["email"],
            len(cleaned["email"] or ""),
            cleaned["category"],
            cleaned["urgency"],
            len(cleaned["description"] or ""),
            cleaned["title"],
        )

        if errors:
            current_app.logger.warning(
                "VALIDATION FAIL: submit_request errors=%s", errors
            )
            flash(_("Please correct the errors below."), "warning")
            return (
                render_template(
                    "submit_request.html",
                    trust_items=trust_items,
                    form_errors=errors,
                ),
                400,
            )

        # ✅ title is NOT NULL in DB
        if not cleaned["title"]:
            cleaned["title"] = (
                _("Заявка: %(category)s", category=cleaned["category"])
                if cleaned["category"]
                else _("Заявка за помощ")
            )

        session["request_draft"] = {
            "name": cleaned["name"],
            "phone": cleaned["phone"],
            "email": cleaned["email"],
            "category": cleaned["category"],
            "urgency": cleaned["urgency"],
            "priority": cleaned["priority"],
            "title": cleaned["title"],
            "description": cleaned["description"],
            "location_text": cleaned["location_text"],
            # Frontend anti-bot timing (optional, can be missing)
            "started_at": cleaned["started_at"],
        }

        return render_template(
            "request_preview.html",
            draft=session["request_draft"],
        )

    trust_items = [
        ("&#10003;", "fas fa-shield-heart", _("Verified volunteers only")),
        ("&#9733;", "fas fa-user-clock", _("Fast matching - no bureaucracy")),
        ("&#9889;", "fas fa-lock", _("We keep your data private")),
    ]
    return render_template("submit_request.html", trust_items=trust_items)


@main_bp.post("/submit_request/confirm")
def submit_request_confirm():
    draft = session.get("request_draft")
    if not draft:
        flash(_("Сесията изтече. Моля, подай заявката отново."), "error")
        return redirect(url_for("main.submit_request"))

    try:
        # --- Server-side anti-bot + rate-limit for magic link (anti-enumeration) ---
        suppress_magic_send = False
        website = (request.form.get("website") or "").strip()
        started_at = (
            request.form.get("started_at") or draft.get("started_at") or ""
        ).strip()

        if website:
            current_app.logger.info("[MAGIC LINK] honeypot hit -> suppressed send")
            suppress_magic_send = True

        try:
            started_ms = int(started_at) if started_at else 0
        except Exception:
            started_ms = 0
        if started_ms and (int(time.time() * 1000) - started_ms) < 2500:
            current_app.logger.info("[MAGIC LINK] too fast -> suppressed send")
            suppress_magic_send = True

        ip = _client_ip()
        email = (draft.get("email") or "").strip().lower()
        email_key = email or ip
        if not _rate_limit_allow(f"ml:req:ip:{ip}", limit=10, window_sec=600):
            current_app.logger.info("[MAGIC LINK] rate-limited ip=%s", ip)
            suppress_magic_send = True
        if not _rate_limit_allow(f"ml:req:email:{email_key}", limit=3, window_sec=600):
            current_app.logger.info("[MAGIC LINK] rate-limited email_key=%s", email_key)
            suppress_magic_send = True

        raw_token = secrets.token_urlsafe(32)
        token_hash = _sha256_hex(raw_token)

        req = Request(
            title=draft.get("title"),
            description=draft.get("description"),
            name=draft.get("name"),
            phone=(draft.get("phone") or None),
            email=(draft.get("email") or None),
            location_text=(draft.get("location_text") or None),
            status="pending",
            priority=draft.get("priority"),
            category=draft.get("category"),
            structure_id=current_structure().id,
        )
        # Legacy fields kept for backwards compatibility with existing /r/<token> links.
        req.requester_token_hash = token_hash
        req.requester_token_created_at = utc_now()

        db.session.add(req)
        db.session.commit()

        # Remember requester email in session for profile view
        try:
            if getattr(req, "email", None):
                session["requester_email"] = (req.email or "").strip().lower()
        except Exception:
            pass

        # Create single-use token row (DB) + build canonical URL.
        expires_at = utc_now() + timedelta(minutes=15)
        try:
            ml = MagicLinkToken(
                token_hash=token_hash,
                purpose="request",
                email=(getattr(req, "email", "") or "").strip().lower(),
                request_id=req.id,
                expires_at=expires_at,
            )
            db.session.add(ml)
            db.session.commit()
        except Exception:
            # If this fails, we still keep legacy token fields; send will use /r/<token>.
            db.session.rollback()

        try:
            base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
            path = url_for("main.magic_link_consume", token=raw_token, _external=False)
            magic_url = (
                f"{base}{path}"
                if base
                else url_for("main.magic_link_consume", token=raw_token, _external=True)
            )
        except Exception:
            magic_url = f"/auth/magic/{raw_token}"

        current_app.logger.info("[MAGIC LINK] request_id=%s url=%s", req.id, magic_url)

        # Send magic link email (best effort)
        try:
            from backend.mail_service import send_notification_email

            recipient = getattr(req, "email", None)
            if recipient and not suppress_magic_send:
                subject = "Confirmez votre demande HelpChain (15 min)"

                # Dedicated template context (no "content" HTML string)
                context = {
                    "magic_link_url": magic_url,
                    "ttl_minutes": 15,
                    "request_id": req.id,
                    # Email microcopy (i18n)
                    "intro_text": _(
                        "Sans mot de passe. Recevez un lien sécurisé par e-mail."
                    ),
                    "button_text": _("Ouvrir mon lien de connexion"),
                    "fallback_text": _(
                        "Si le bouton ne fonctionne pas, copiez-collez ce lien :"
                    ),
                    "privacy_line": _("Données minimales, respect RGPD"),
                    "ignore_line": _(
                        "Si vous n’êtes pas à l’origine de cette demande, ignorez cet e-mail."
                    ),
                }

                send_notification_email(
                    recipient,
                    subject,
                    "emails/magic_link.html",
                    context,
                    purpose="request_magic_link",
                )
            elif recipient and suppress_magic_send:
                current_app.logger.info(
                    "[MAGIC LINK] send suppressed (antibot/rate-limit)"
                )
        except Exception as e:
            current_app.logger.warning("[EMAIL] magic link send failed: %s", e)

        session.pop("request_draft", None)
        session["last_request_id"] = req.id

        category = draft.get("category")
        urgency = draft.get("urgency")
        is_emergency = category in ("emergency", "urgent") or urgency in (
            "critical",
            "emergency",
            "urgent",
        )

        app = current_app._get_current_object()
        if (
            is_emergency
            and hasattr(app, "can_send_emergency_email")
            and app.can_send_emergency_email()
        ):
            if hasattr(app, "send_emergency_email"):
                app.send_emergency_email(req)
            if hasattr(app, "mark_emergency_email_sent"):
                app.mark_emergency_email_sent()

        log_security_event(
            "request_submitted",
            actor_type="anonymous",
            meta={"request_id": req.id, "category": getattr(req, "category", None)},
        )

        return redirect(url_for("main.profile"))

    except Exception as e:
        current_app.logger.exception("CONFIRM FAILED: %s", e)
        db.session.rollback()
        flash("Грешка при записване. Моля, опитай отново.", "error")
        return redirect(url_for("main.submit_request"))


@main_bp.get("/success")
def success():
    request_id = request.args.get("request_id") or session.get("last_request_id")
    is_admin = bool(session.get("admin_logged_in"))
    return (
        render_template("success.html", request_id=request_id, is_admin=is_admin),
        200,
    )


@main_bp.get("/pilot", endpoint="pilot")
def pilot_dashboard():
    now = utc_now()
    week_ago = now - timedelta(days=7)
    since_14d = now - timedelta(days=14)

    tenant_filter = Request.structure_id == _current_structure_id()
    not_deleted = Request.deleted_at.is_(None)

    total_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted)
        .scalar()
        or 0
    )

    open_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status.notin_(["done", "rejected"]))
        .scalar()
        or 0
    )

    closed_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status.in_(["done", "rejected"]))
        .scalar()
        or 0
    )

    closed_last_7d = (
        db.session.query(func.count(Request.id))
        .filter(
            tenant_filter,
            not_deleted,
            Request.completed_at.isnot(None),
            Request.completed_at >= week_ago,
        )
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
        .filter(
            tenant_filter,
            not_deleted,
            Request.completed_at.isnot(None),
            Request.created_at.isnot(None),
        )
        .scalar()
    )
    avg_resolution_hours = (
        float(avg_resolution_hours) if avg_resolution_hours is not None else None
    )

    unassigned_48h = (
        db.session.query(func.count(Request.id))
        .filter(
            tenant_filter,
            not_deleted,
            Request.status.notin_(["done", "rejected"]),
            Request.owner_id.is_(None),
            Request.created_at <= (now - timedelta(days=2)),
        )
        .scalar()
        or 0
    )

    stale_7d = (
        db.session.query(func.count(Request.id))
        .filter(
            tenant_filter,
            not_deleted,
            Request.status.notin_(["done", "rejected"]),
            Request.created_at <= (now - timedelta(days=7)),
        )
        .scalar()
        or 0
    )

    high_open = (
        db.session.query(func.count(Request.id))
        .filter(
            tenant_filter,
            not_deleted,
            Request.status.notin_(["done", "rejected"]),
            Request.priority == "high",
        )
        .scalar()
        or 0
    )

    status_rows = (
        db.session.query(Request.status, func.count(Request.id))
        .filter(tenant_filter, not_deleted)
        .group_by(Request.status)
        .order_by(func.count(Request.id).desc())
        .all()
    )
    status_labels = [r[0] or "unknown" for r in status_rows]
    status_counts = [int(r[1]) for r in status_rows]

    cat_rows = (
        db.session.query(Request.category, func.count(Request.id))
        .filter(tenant_filter, not_deleted)
        .group_by(Request.category)
        .order_by(func.count(Request.id).desc())
        .all()
    )
    cat_labels = [r[0] or "unknown" for r in cat_rows]
    cat_counts = [int(r[1]) for r in cat_rows]

    trend_rows = (
        db.session.query(func.date(Request.created_at), func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.created_at >= since_14d)
        .group_by(func.date(Request.created_at))
        .order_by(func.date(Request.created_at))
        .all()
    )
    trend_dates = [str(r[0]) for r in trend_rows]
    trend_counts = [int(r[1]) for r in trend_rows]

    total_volunteers = (
        db.session.query(func.count(Volunteer.id))
        .filter(Volunteer.is_active.is_(True))
        .scalar()
        or 0
    )
    countries = len(COUNTRIES_SUPPORTED)

    impact = {
        "total": int(total_requests),
        "open": int(open_requests),
        "closed": int(closed_requests),
        "volunteers": int(total_volunteers),
        "active_volunteers": int(total_volunteers),
        "countries": int(countries),
        "closed_last_7d": int(closed_last_7d),
        "avg_resolution_hours": avg_resolution_hours,
        "unassigned_48h": int(unassigned_48h),
        "stale_7d": int(stale_7d),
        "high_open": int(high_open),
        "status_labels": status_labels,
        "status_counts": status_counts,
        "cat_labels": cat_labels,
        "cat_counts": cat_counts,
        "trend_dates": trend_dates,
        "trend_counts": trend_counts,
        "generated_at": now,
        "window_days": 14,
    }

    resp = make_response(render_template("pilot_dashboard.html", impact=impact))
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@main_bp.get("/api/pilot/metrics")
def pilot_metrics():
    tenant_filter = Request.structure_id == _current_structure_id()
    not_deleted = Request.deleted_at.is_(None)

    total_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted)
        .scalar()
        or 0
    )
    open_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status.notin_(["done", "rejected"]))
        .scalar()
        or 0
    )
    helped_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status == "done")
        .scalar()
        or 0
    )
    closed_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status.in_(["done", "rejected"]))
        .scalar()
        or 0
    )
    total_volunteers = (
        db.session.query(func.count(Volunteer.id))
        .filter(Volunteer.is_active.is_(True))
        .scalar()
        or 0
    )
    countries = len(COUNTRIES_SUPPORTED)

    impact = {
        "total": int(total_requests),
        "open": int(open_requests),
        "helped": int(helped_requests),
        "closed": int(closed_requests),
        "volunteers": int(total_volunteers),
        "active_volunteers": int(total_volunteers),
        "countries": int(countries),
    }
    return jsonify(impact), 200


@main_bp.get("/api/pilot-kpi")
def pilot_kpi_api():
    # v1: marketing-safe counters (read-only)
    tenant_filter = Request.structure_id == _current_structure_id()
    not_deleted = Request.deleted_at.is_(None)

    helped_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status == "done")
        .scalar()
        or 0
    )

    closed_requests = (
        db.session.query(func.count(Request.id))
        .filter(tenant_filter, not_deleted, Request.status.in_(["done", "rejected"]))
        .scalar()
        or 0
    )

    active_volunteers = (
        db.session.query(func.count(Volunteer.id))
        .filter(Volunteer.is_active.is_(True))
        .scalar()
        or 0
    )

    countries_count = len(COUNTRIES_SUPPORTED)

    resp = jsonify(
        {
            "active_volunteers": int(active_volunteers),
            "helped": int(helped_requests),
            "closed": int(closed_requests),
            "countries": int(countries_count),
        }
    )
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp, 200


@main_bp.route("/faq")
def faq():
    return render_template("faq.html")


@main_bp.get("/professionnels")
def professionnels():
    return render_template("professionnels.html"), 200


@main_bp.route("/professionnels/pilote", methods=["GET", "POST"])
def professionnels_pilote():
    if request.method == "GET":
        return render_template("professionnels_pilote.html"), 200

    email = (request.form.get("email") or "").strip().lower()
    full_name = (request.form.get("full_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    city = (request.form.get("city") or "").strip()
    profession = (request.form.get("profession") or "").strip()
    organization = (request.form.get("organization") or "").strip()
    availability = (request.form.get("availability") or "").strip()
    message = (request.form.get("message") or "").strip()

    if not email or "@" not in email or not profession:
        flash("Merci de renseigner au minimum votre e-mail et votre métier.", "error")
        return render_template("professionnels_pilote.html"), 400

    existing = (
        ProfessionalLead.query.filter(ProfessionalLead.email == email)
        .order_by(ProfessionalLead.id.desc())
        .first()
    )

    if existing:
        existing.city = city or existing.city
        existing.phone = phone or existing.phone
        existing.message = (message or "").strip() or existing.message
        existing.locale = (
            session.get("lang") or str(babel_get_locale() or "")
        ).strip() or existing.locale
        existing.ip = _client_ip() or existing.ip
        existing.user_agent = (request.headers.get("User-Agent") or "")[
            :255
        ] or existing.user_agent
        existing.source = "professionnels_pilote"
        db.session.commit()
        current_app.logger.info(
            "[PRO-LEAD] dedup hit email=%s existing_id=%s created_at=%s",
            email,
            existing.id,
            existing.created_at,
        )
        # Same UX either way: return success without inserting duplicate lead.
        return render_template("professionnels_pilote_thanks.html", lead=existing), 200

    lead = ProfessionalLead(
        email=email,
        full_name=full_name or None,
        phone=phone or None,
        city=city or None,
        profession=profession,
        organization=organization or None,
        availability=availability or None,
        message=message or None,
        locale=((session.get("lang") or str(babel_get_locale() or "")).strip() or None),
        ip=_client_ip(),
        user_agent=((request.headers.get("User-Agent") or "")[:255] or None),
        source="professionnels_pilote",
        created_at=datetime.now(UTC),
    )
    db.session.add(lead)
    db.session.commit()

    try:
        from backend.mail_service import send_notification_email

        admin_to = (current_app.config.get("PRO_LEADS_NOTIFY_TO") or "").strip()
        if not admin_to:
            admin_to = (current_app.config.get("ADMIN_NOTIFY_EMAIL") or "").strip()

        ctx = {
            "lead_id": lead.id,
            "email": lead.email,
            "full_name": lead.full_name,
            "phone": lead.phone,
            "city": lead.city,
            "profession": lead.profession,
            "organization": lead.organization,
            "availability": lead.availability,
            "message": lead.message,
            "created_at": lead.created_at,
            "source": lead.source,
            "locale": lead.locale,
            "ip": lead.ip,
            "user_agent": lead.user_agent,
            "admin_url": f"{request.host_url.rstrip('/')}/admin/professional-leads",
        }
        if admin_to:
            subject = "[HelpChain] Nouveau lead professionnel"
            send_notification_email(
                admin_to,
                subject,
                "emails/professional_lead_notify.html",
                ctx,
            )
        else:
            current_app.logger.info("[PRO-LEAD] notify skipped: no PRO_LEADS_NOTIFY_TO")
    except Exception:
        current_app.logger.exception(
            "[PRO-LEAD] notify email failed lead_id=%s", lead.id
        )

    return render_template("professionnels_pilote_thanks.html", lead=lead), 200


@main_bp.route("/success_stories")
def success_stories():
    return render_template("success_stories.html")


@main_bp.route("/contact")
def contact():
    return render_template("contact.html"), 200


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/legal")
def legal():
    # FR-first legal page (Mentions legales + RGPD). Keep content in template.
    return render_template("legal.html")


@main_bp.get("/mentions-legales")
@main_bp.get("/mentions_legales")
def mentions_legales():
    return legal()


@main_bp.get("/video-chat")
def video_chat():
    return render_template("video_chat.html")


# --- Legacy/compat pages (minimal but real) ---
@main_bp.get("/volunteer/settings")
def volunteer_settings():
    return render_template("volunteer_settings.html"), 200


@main_bp.get("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html"), 200


@main_bp.get("/volunteer/chat")
def volunteer_chat():
    return render_template("volunteer_chat.html"), 200


@main_bp.get("/volunteer/reports")
def volunteer_reports():
    return render_template("volunteer_reports.html"), 200


@main_bp.get("/my-requests")
def my_requests():
    return render_template("dashboard_requester.html"), 200


@main_bp.get("/feedback")
def feedback():
    return redirect(url_for("main.contact"), code=302)


@main_bp.get("/forgot-password")
def forgot_password():
    return redirect(url_for("main.become_volunteer"), code=302)


@main_bp.post("/submit_request/resend")
def submit_request_resend():
    return redirect(url_for("main.submit_request"), code=302)


@main_bp.get("/r/<int:req_id>")
def request_public(req_id: int):
    return redirect(url_for("main.submit_request"), code=302)


@main_bp.post("/set-language")
@main_bp.post("/set_language")
def set_language():
    supported = {
        "fr", "en", "es", "it", "de", "ar", "br", "ca", "cs", "co", "cy", "da",
        "et", "eu", "sw", "mfe", "lv", "lb", "lt", "hu", "nl", "no", "oc", "pl",
        "pt", "ro", "sk", "sl", "fi", "sv", "vi", "tr", "el", "bg", "ru", "uk",
        "yi", "he", "ps", "hi", "th", "ko", "zh", "ja",
    }
    lang = (request.form.get("lang") or "").strip().lower()
    if lang not in supported:
        lang = "bg"

    session["lang"] = lang
    session.modified = True

    next_url = request.form.get("next") or request.referrer or url_for("main.index")
    resp = make_response(redirect(next_url))
    resp.set_cookie("hc_lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@main_bp.route("/category_help/<category>", methods=["GET"])
def category_help(category: str):
    # Display name fallback (ако нямаме CATEGORIES)
    category_names = {
        "food": "Храна",
        "medical": "Медицинска помощ",
        "transport": "Транспорт",
        "other": "Друго",
    }
    category_display = category_names.get(category, (category or "").title())

    # Canonical slug (alias support)
    canonical = ALIASES.get(category, category)

    # Category info (from CATEGORIES)
    data = CATEGORIES.get(canonical)
    if data:
        title_bg = data.get("content", {}).get("title", {}).get("bg")
        icon = (
            data.get("ui", {}).get("icon")
            or "fa-solid fa-circle-question text-secondary"
        )
        severity = data.get("ui", {}).get("severity")
        color = "danger" if severity == "critical" else "primary"

        category_info = {
            "slug": canonical,
            "name": title_bg or category_display,
            "icon": icon,
            "color": color,
        }
    else:
        category_info = {
            "slug": canonical,
            "name": category_display,
            "icon": "fa-solid fa-circle-question text-secondary",
            "color": "primary",
        }

    # Category cards in /categories lead to request submission with preselected category.
    return redirect(url_for("main.submit_request", category=canonical), code=302)


@main_bp.get("/sw.js")
def service_worker():
    # Serve /sw.js from src/static/sw.js
    return send_from_directory(current_app.static_folder, "sw.js")
