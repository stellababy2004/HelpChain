from flask import (
    Blueprint,
    flash,
    redirect,
    jsonify,
    render_template,
    request,
    session,
    url_for,
    current_app,
    send_from_directory,
    make_response,
    abort,
)
from types import SimpleNamespace
from werkzeug.security import check_password_hash
from flask_babel import get_locale as babel_get_locale, gettext as _
from flask_wtf import FlaskForm
from flask_login import login_required, current_user, logout_user
from datetime import timedelta, datetime
import secrets
import hashlib

from flask_limiter.util import get_remote_address

from ..extensions import limiter
from ..models import Request, Volunteer, db, utc_now, canonical_role, Notification, VolunteerAction, RequestActivity
from ..models.volunteer_interest import VolunteerInterest
from ..category_data import CATEGORIES, ALIASES, COMMON
from sqlalchemy import or_, func, desc
from functools import wraps
from urllib.parse import urlparse, urljoin
from ..statuses import normalize_request_status
from ..security_logging import log_security_event
from ..notifications.inapp import ensure_new_match_notifications
from ..authz import can_view_notification, can_view_request

COUNTRIES_SUPPORTED = ["FR", "CH", "CA", "BG"]

main_bp = Blueprint("main", __name__)


def email_or_ip_key():
    """Prefer per-email throttling; fall back to IP for anonymous abuse control."""
    email = (request.form.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    return get_remote_address()


def has_control_chars(text: str) -> bool:
    """Detect non-printable control chars (excluding common whitespace)."""
    if not text:
        return False
    return any(ord(ch) < 32 and ch not in ("\t", "\n", "\r") for ch in text)


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


def get_safe_next(default_endpoint: str):
    nxt = request.args.get("next")
    if nxt and is_safe_url(nxt):
        return nxt
    return default_endpoint


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


def is_request_matching_volunteer(request_obj, volunteer_obj, interested_request_ids: set[int] | None = None):
    """MVP matching (V2.2.A): status open + volunteer active + profile complete + not already interested."""
    if not request_obj or not volunteer_obj:
        return False

    if (getattr(request_obj, "status", "") or "").lower() != "open":
        return False

    if not getattr(volunteer_obj, "is_active", False):
        return False

    # profile completeness (location + availability)
    if not (getattr(volunteer_obj, "location", None) and getattr(volunteer_obj, "availability", None)):
        return False

    # exclude assigned/archived/deleted
    if getattr(request_obj, "assigned_volunteer_id", None) is not None:
        return False
    if getattr(request_obj, "is_archived", False):
        return False
    if getattr(request_obj, "deleted_at", None) is not None:
        return False

    if interested_request_ids and getattr(request_obj, "id", None) in interested_request_ids:
        return False

    # Geo/skills matching postponed (later versions)
    return True


def require_volunteer_login(fn):
    """Minimal access control using session flag (non-Flask-Login)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("volunteer_id"):
            return redirect(url_for("main.volunteer_login", next=request.full_path), code=303)
        return fn(*args, **kwargs)

    return wrapper


def _current_volunteer():
    vid = session.get("volunteer_id")
    if not vid:
        return None
    try:
        return Volunteer.query.get(int(vid))
    except Exception:
        return None


# Minimal form to issue CSRF tokens for inline button actions
class CSRFOnlyForm(FlaskForm):
    pass


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

    return {
        "url_lang": url_lang,
        "safe_url_for": safe_url_for,
    }


@main_bp.route("/", methods=["GET"])
def index():
    """Главна страница"""
    latest_requests = []
    try:
        latest_requests = (
            Request.query
            .filter(Request.deleted_at.is_(None))
            .filter(Request.is_archived == 0)
            .order_by(Request.created_at.desc())
            .limit(6)
            .all()
        )
    except Exception as e:
        current_app.logger.warning("Home latest_requests skipped: %s", e)
        latest_requests = []
    return render_template("home_new_slim.html", latest_requests=latest_requests), 200


@main_bp.get("/logout", endpoint="logout")
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
        remember_cookie = current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
        resp.delete_cookie(remember_cookie, path="/")
    except Exception:
        pass

    return resp


@main_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    role = (getattr(current_user, "role_canon", None) or canonical_role(getattr(current_user, "role", None)))

    if role in ("admin", "superadmin"):
        return redirect(url_for("admin.admin_requests"))

    if role == "requester":
        my_requests = (
            Request.query
            .filter(Request.user_id == current_user.id)
            .populate_existing()
            .order_by(desc(Request.created_at))
            .limit(20)
            .all()
        )
        counts = dict(
            ( (s or "open"), c )
            for s, c in
            db.session.query(Request.status, func.count(Request.id))
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
        return render_template("dashboard_requester.html", my_requests=my_requests, kpi=kpi)

    if role in ("volunteer", "professional"):
        assigned = (
            Request.query
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
            ( (s or "open"), c )
            for s, c in
            db.session.query(Request.status, func.count(Request.id))
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
        role = (getattr(current_user, "role_canon", None) or canonical_role(getattr(current_user, "role", None)))
        if role in ("admin", "superadmin"):
            return redirect(url_for("admin.admin_requests"))
        if role in ("volunteer", "professional"):
            return redirect(url_for("main.dashboard"))

    # Requester via session-stored email
    requester_email = (session.get("requester_email") or "").strip().lower()
    if not requester_email:
        return redirect(url_for("main.submit_request"))

    my_requests = (
        Request.query
        .filter(func.lower(Request.email) == requester_email)
        .order_by(desc(Request.created_at))
        .limit(20)
        .all()
    )
    rows = (
        db.session.query(Request.status, func.count(Request.id))
        .filter(func.lower(Request.email) == requester_email)
        .group_by(Request.status)
        .all()
    )
    counts = { (s or "open"): c for s, c in rows }
    kpi = {
        "open": counts.get("open", 0),
        "in_progress": counts.get("in_progress", 0),
        "done": counts.get("done", 0),
        "cancelled": counts.get("cancelled", 0),
    }
    return render_template("profile_requester.html", kpi=kpi, my_requests=my_requests, requester_email=requester_email)


@main_bp.get("/requester/logout")
def requester_logout():
    session.pop("requester_email", None)
    flash(_("Your session has been cleared."), "info")
    return redirect(url_for("main.submit_request"))


@main_bp.get("/r/<token>")
def requester_magic_profile(token: str):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reqs = (
        Request.query
        .filter(Request.requester_token_hash == token_hash)
        .order_by(desc(Request.created_at))
        .all()
    )
    if not reqs:
        abort(404)

    counts = {"open": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    for r in reqs:
        s = (r.status or "open").lower()
        if s in counts:
            counts[s] += 1

    return render_template(
        "profile_requester.html",
        kpi=counts,
        my_requests=reqs,
        requester_magic=True,
    )


@main_bp.get("/set-lang/<lang>")
def set_lang_switch(lang):
    lang = (lang or "").lower().strip()
    if lang not in ("bg", "fr", "en"):
        lang = "en"

    session["lang"] = lang

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
        locale = "en"

    session["lang"] = locale
    next_url = request.args.get("next") or url_for("main.index")

    resp = make_response(redirect(next_url))
    resp.set_cookie("hc_lang", locale, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@main_bp.route("/categories", methods=["GET"])
@limiter.limit("120 per minute")
def categories():
    """Списък с всички категории"""
    locale_code = (str(babel_get_locale()) or "en").split("_", 1)[0].lower()

    def pick_locale(values):
        if not isinstance(values, dict):
            return values
        return values.get(locale_code) or values.get("en") or values.get("bg") or next(iter(values.values()), "")

    items = []
    for key, value in CATEGORIES.items():
        items.append(
            {
                "slug": key,
                "name": pick_locale(value.get("content", {}).get("title", {})),
                "description": pick_locale(value.get("content", {}).get("intro", {})),
                "icon": value["ui"].get("icon", "fa-solid fa-question-circle text-secondary"),
                "color": "primary" if value["ui"].get("severity") != "critical" else "danger",
            }
        )
    return render_template("all_categories.html", categories=items)


@main_bp.route("/achievements", methods=["GET"])
def achievements():
    if not session.get("volunteer_logged_in"):
        return redirect(url_for("main.volunteer_login"))

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
    current_app.logger.info(
        "volunteer_login cfg bypass_enabled=%s bypass_email=%s args_dev=%s",
        current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED"),
        current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL"),
        request.args.get("dev"),
    )
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        generic_msg = _("If the email is valid, you will receive a login link.")

        log_security_event("magic_link_requested", actor_type="anonymous", meta={"flow": "volunteer"})

        if current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED") and email == current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL"):
            v = Volunteer.query.filter_by(email=email).first()
            if not v:
                v = Volunteer(email=email, is_active=True)
                db.session.add(v)
                db.session.commit()

            session.clear()
            session["volunteer_id"] = v.id
            session["volunteer_logged_in"] = True
            log_security_event("volunteer_dev_bypass_login", actor_type="volunteer", actor_id=v.id)
            return redirect(url_for("main.volunteer_dashboard"))

        if not email:
            flash(generic_msg, "info")
            return render_template("volunteer_login.html", minimal_page=True), 200

        volunteer = Volunteer.query.filter(Volunteer.email.ilike(email)).first()

        if not volunteer or not getattr(volunteer, "is_active", True):
            flash(generic_msg, "info")
            return render_template("volunteer_login.html", minimal_page=True), 200

        session["volunteer_id"] = int(volunteer.id)
        session.permanent = True
        session["just_logged_in"] = True

        try:
            volunteer.last_activity = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
        target = get_safe_next(url_for("main.volunteer_dashboard"))
        if not getattr(volunteer, "volunteer_onboarded", False):
            return redirect(url_for("main.volunteer_onboarding", next=target), code=303)
        return redirect(target, code=303)

    prefill_email = ""
    if current_app.config.get("VOLUNTEER_DEV_BYPASS_ENABLED") and request.args.get("dev") == "1":
        prefill_email = current_app.config.get("VOLUNTEER_DEV_BYPASS_EMAIL") or ""

    return render_template("volunteer_login.html", minimal_page=True, prefill_email=prefill_email), 200

    return render_template("volunteer_login.html", minimal_page=True), 200


@main_bp.post("/volunteer/logout")
def volunteer_logout():
    session.pop("volunteer_id", None)
    session.pop("just_logged_in", None)
    session.pop("demo_pending", None)
    return redirect(url_for("main.index"), code=303)


@main_bp.route("/become_volunteer", methods=["GET", "POST"])
def become_volunteer():
    """Public landing + submission endpoint for new volunteers."""
    if request.method == "POST":
        # TODO: collect and persist the submitted volunteer data
        return redirect(url_for("main.volunteer_confirmation"))

    not_required_items = [
        ("fas fa-ban", _("Да поемаш рискове или да заместваш спешни служби.")),
        ("fas fa-shield-alt", _("Да помагаш, ако не се чувстваш комфортно или безопасно.")),
        ("fas fa-hand-paper", _("Да приемаш задължителни ангажименти - отказът винаги е приемлив.")),
    ]

    return render_template(
        "become_volunteer.html",
        not_required_items=not_required_items,
    ), 200


@main_bp.get("/volunteer/confirmation")
def volunteer_confirmation():
    """Confirmation screen after submitting volunteer interest."""
    return render_template("volunteer_confirmation.html"), 200


@main_bp.get("/volunteer/onboarding")
@require_volunteer_login
def volunteer_onboarding():
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login"))
    if getattr(volunteer, "volunteer_onboarded", False):
        return redirect(get_safe_next(url_for("main.volunteer_dashboard")))
    return render_template("volunteer_onboarding.html"), 200


@main_bp.post("/volunteer/onboarding")
@require_volunteer_login
def volunteer_onboarding_submit():
    volunteer_id = session.get("volunteer_id")
    if not volunteer_id:
        return redirect(url_for("main.volunteer_login"))

    volunteer = Volunteer.query.get(volunteer_id)
    if not volunteer:
        return redirect(url_for("main.volunteer_login"))

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
        return redirect(url_for("main.volunteer_login", next=request.path))
    if not getattr(volunteer, "volunteer_onboarded", False):
        return redirect(url_for("main.volunteer_onboarding", next=request.full_path), code=303)

    just_logged_in = session.pop("just_logged_in", None)

    open_requests = Request.query.filter_by(status="open").all()

    my_interest_req_ids = set(
        rid for (rid,) in db.session.query(VolunteerInterest.request_id)
        .filter(VolunteerInterest.volunteer_id == volunteer.id)
        .all()
    )

    # Show matches even if the volunteer already expressed interest.
    # The dashboard will reflect interest status via badges/CTAs.
    matched_requests = [
        r for r in open_requests
        if is_request_matching_volunteer(r, volunteer, interested_request_ids=None)
    ]

    # V2.2.A — in-app notification: create once per (volunteer, request)
    # Only for "fresh" matches (no interest yet).
    candidate_requests = [r for r in matched_requests if getattr(r, "id", None) and r.id not in my_interest_req_ids]
    if candidate_requests:
        matched_ids = [r.id for r in candidate_requests if getattr(r, "id", None)]

        existing = set(
            rid for (rid,) in db.session.query(Notification.request_id)
            .filter(
                Notification.volunteer_id == volunteer.id,
                Notification.type == "new_match",
                Notification.request_id.in_(matched_ids),
            )
            .all()
        )

        new_notifs = []
        for r in candidate_requests:
            if r.id in existing:
                continue
            new_notifs.append(
                Notification(
                    volunteer_id=volunteer.id,
                    type="new_match",
                    request_id=r.id,
                    title="New match",
                    body=(r.title or "")[:200],
                    is_read=False,
                )
            )

        if new_notifs:
            db.session.add_all(new_notifs)
            db.session.commit()

    pending_ids = set(
        rid for (rid,) in db.session.query(VolunteerInterest.request_id)
        .filter(
            VolunteerInterest.volunteer_id == volunteer.id,
            VolunteerInterest.status == "pending",
        ).all()
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
        if not my_first_closed_req and req_status in {"closed", "done", "completed", "resolved"}:
            my_first_closed_req = row

    # --- Generate match notifications lazily (MVP) ---
    profile_complete = bool(volunteer.location) and bool(volunteer.availability)
    if volunteer.is_active and profile_complete:
        eligible_matches = [r for r in matched_requests if r.id not in my_interest_req_ids]
        ensure_new_match_notifications(volunteer_id=volunteer.id, request_rows=eligible_matches)

    current_app.logger.info(
        "Matching check",
        extra={
            "volunteer_id": volunteer.id,
        "matched_requests": len(matched_requests),
    },
    )

    csrf_form = CSRFOnlyForm()

    actions = db.session.query(VolunteerAction.request_id, VolunteerAction.action).filter(
        VolunteerAction.volunteer_id == volunteer.id
    ).all()
    my_actions_by_req_id = {rid: act for rid, act in actions}

    unread_match_notifications = (
        Notification.query.filter_by(volunteer_id=volunteer.id, is_read=False, type="new_match")
        .order_by(Notification.created_at.desc())
        .all()
    )
    unread_count = Notification.query.filter_by(volunteer_id=volunteer.id, is_read=False).count()

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
                    "main.volunteer_request_details", req_id=my_first_approved_req["req"].id
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
        first_match = unread_match_notifications[0]
        notifications.append(
            {
                "kind": "new_match",
                "title": notif_lang["new_match"]["title"],
                "body": notif_lang["new_match"]["body"],
                "cta_label": notif_lang["new_match"]["cta"],
                "cta_href": url_for(
                    "main.volunteer_request_details", req_id=first_match.request_id
                ),
                "tone": "primary",
            }
        )
        badge_count = 1

    return render_template(
        "volunteer_dashboard.html",
        volunteer=volunteer,
        matches=matched_requests,
        just_logged_in=bool(just_logged_in),
        pending_ids=pending_ids,
        interest_by_req_id=interest_by_req_id,
        my_pending=my_pending,
        my_approved=my_approved,
        my_rejected=my_rejected,
        notifications=notifications,
        volunteer_badge_count=badge_count,
        unread_count=unread_count,
        my_actions_by_req_id=my_actions_by_req_id,
        csrf_form=csrf_form,
    ), 200


@main_bp.get("/volunteer/requests/<int:req_id>")
@require_volunteer_login
def volunteer_request_details(req_id: int):
    """Детайли за заявка, достъпни за логнат доброволец."""
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)
    try:
        db.session.refresh(req)
    except Exception:
        pass

    if not can_view_request(volunteer, req, db):
        abort(404)

    vi = (
        VolunteerInterest.query.filter_by(
            volunteer_id=volunteer.id, request_id=req.id
        )
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
        VolunteerAction.query
        .filter_by(request_id=req.id, volunteer_id=volunteer.id)
        .order_by(VolunteerAction.updated_at.desc(), VolunteerAction.created_at.desc(), VolunteerAction.id.desc())
        .first()
    )

    # опционален контрол: показваме само ако е match/отворена
    # if not is_request_matching_volunteer(req, volunteer):
    #     abort(403)

    # Mark related match notification as read (if any)
    try:
        changed = Notification.query.filter_by(
            volunteer_id=volunteer.id, request_id=req.id, type="new_match", is_read=False
        ).update({"is_read": True, "read_at": datetime.utcnow()})
        if changed:
            db.session.commit()
    except Exception:
        db.session.rollback()

    csrf_form = CSRFOnlyForm()

    return render_template(
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
        csrf_form=csrf_form,
    ), 200


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
    return render_template(
        "volunteer_request_details.html",
        req=demo_req,
        volunteer=volunteer,
        is_pending=already_pending,
        already_pending=already_pending,
        already_approved=False,
        already_rejected=False,
        is_demo=True,
    ), 200


@main_bp.post("/volunteer/requests/<int:req_id>/help")
@require_volunteer_login
def volunteer_help(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

    current_app.logger.info("VOL_HELP DB=%s", db.engine.url)
    current_app.logger.info("VOL_HELP req_id=%s", req_id)

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

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

    current_app.logger.info("VOL_HELP about to commit volunteer_id=%s request_id=%s", volunteer.id, req.id)
    db.session.commit()
    current_app.logger.info("VOL_HELP committed interest_id=%s status=%s", interest.id, interest.status)

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
            action=f"volunteer_{action_value.lower()}",
            old_value=old_action,
            new_value=action_value,
        )
    )
    db.session.commit()
    return row


@main_bp.post("/volunteer/requests/<int:req_id>/can-help")
@require_volunteer_login
def volunteer_can_help(req_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

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
        return redirect(url_for("main.volunteer_login", next=request.path))

    req = db.session.get(Request, req_id)
    if not req:
        abort(404)

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
    flash("✅ Благодарим! Интересът ти е отбелязан (демо).", "success")
    return redirect(url_for("main.volunteer_request_demo"))


@main_bp.get("/volunteer/notifications")
@require_volunteer_login
def volunteer_notifications():
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login"))

    # Volunteer UI: notifications are primarily keyed by `volunteer_id`.
    owner_col = getattr(Notification, "volunteer_id", None) or getattr(Notification, "user_id", None)
    if owner_col is None:
        abort(500)
    notifs = (
        Notification.query.filter(owner_col == volunteer.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = Notification.query.filter(
        owner_col == volunteer.id, Notification.is_read == False  # noqa: E712
    ).count()

    return render_template(
        "volunteer_notifications.html",
        notifications=notifs,
        unread_count=unread_count,
    ), 200


@main_bp.post("/volunteer/notifications/<int:notif_id>/open")
@require_volunteer_login
def volunteer_notification_open(notif_id: int):
    volunteer = _current_volunteer()
    if not volunteer:
        return redirect(url_for("main.volunteer_login"))

    n = Notification.query.get_or_404(notif_id)

    if not can_view_notification(volunteer, n):
        abort(404)

    changed = False
    if not n.is_read:
        n.is_read = True
        n.read_at = utc_now()
        changed = True
    if hasattr(n, "status") and getattr(n, "status", None) == "UNREAD":
        n.status = "READ"
        changed = True
    if changed:
        db.session.commit()

    if n.request_id:
        return redirect(url_for("main.volunteer_request_details", req_id=n.request_id))

    return redirect(url_for("main.volunteer_notifications"))


@main_bp.route("/volunteer/profile", methods=["GET", "POST"])
@require_volunteer_login
def volunteer_profile():
    volunteer = _current_volunteer()

    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

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
    description = (form.get("description") or form.get("problem") or form.get("message") or "").strip()
    return category, urgency, description


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
        current_app.logger.warning("website(honeypot)='%s'", (request.form.get("website") or "").strip())
        # Honeypot anti-bot field (ако се задейства, искам да го ВИДИШ)
        website = (request.form.get("website") or "").strip()
        if website:
            current_app.logger.warning("Honeypot triggered on submit_request: website=%r", website)
            # Pretend success to avoid bot feedback loops
            return render_template("submit_request.html", trust_items=trust_items, success=True), 200

        category, urgency, description = normalize_request_form(request.form)

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

        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        email = (request.form.get("email") or "").strip()
        location_text = (request.form.get("location_text") or request.form.get("location") or "").strip()
        title = (request.form.get("title") or "").strip()

        current_app.logger.warning(
            "Parsed: name=%r(len=%s) phone=%r(len=%s) email=%r(len=%s) category=%r urgency=%r desc_len=%s title=%r",
            name, len(name or ""),
            phone, len(phone or ""),
            email, len(email or ""),
            category, urgency,
            len(description or ""),
            title,
        )

        MAX_NAME_LEN = 80
        MAX_TITLE_LEN = 120
        MAX_DESC_LEN = 2000
        MAX_LOCATION_LEN = 120

        for label, value, max_len in (
            ("name", name, MAX_NAME_LEN),
            ("title", title, MAX_TITLE_LEN),
            ("description", description, MAX_DESC_LEN),
            ("location", location_text, MAX_LOCATION_LEN),
        ):
            if len(value) > max_len:
                current_app.logger.warning("VALIDATION FAIL: %s too long (%s > %s)", label, len(value), max_len)
                flash(_("Please shorten the %(field)s.", field=_("text") if label == "description" else label), "error")
                return redirect(url_for("main.submit_request"))

        for label, value in (
            ("name", name),
            ("title", title),
            ("description", description),
            ("location_text", location_text),
        ):
            if has_control_chars(value):
                current_app.logger.warning("VALIDATION FAIL: control chars in %s", label)
                flash(_("Invalid characters detected."), "error")
                return redirect(url_for("main.submit_request"))

        # ✅ Server-side validation (точно както UX-а)
        if len(name) < 2:
            current_app.logger.warning("VALIDATION FAIL: name < 2")
            flash("Моля, въведете име (поне 2 символа).", "error")
            return redirect(url_for("main.submit_request"))

        if len(description) < 10:
            current_app.logger.warning("VALIDATION FAIL: description < 10")
            flash("Моля, опишете проблема (поне 10 символа).", "error")
            return redirect(url_for("main.submit_request"))

        if not phone and not email:
            current_app.logger.warning("VALIDATION FAIL: no phone and no email")
            flash("Моля, въведете поне телефон или имейл.", "error")
            return redirect(url_for("main.submit_request"))

        # ✅ title is NOT NULL in DB
        if not title:
            title = f"Заявка: {category}" if category else "Заявка за помощ"

        # ✅ category default (DB показва default general)
        if not category:
            category = "general"

        session["request_draft"] = {
            "name": name,
            "phone": phone,
            "email": email,
            "category": category,
            "urgency": urgency,
            "priority": priority,
            "title": title,
            "description": description,
            "location_text": location_text,
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
@limiter.limit("5 per minute")
def submit_request_confirm():
    draft = session.get("request_draft")
    if not draft:
        flash("Сесията изтече. Моля, подай заявката отново.", "error")
        return redirect(url_for("main.submit_request"))

    try:
        token = secrets.token_urlsafe(32)

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
        )
        # Magic link fields (hash only)
        req.requester_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        req.requester_token_created_at = utc_now()

        db.session.add(req)
        db.session.commit()

        # Remember requester email in session for profile view
        try:
            if getattr(req, "email", None):
                session["requester_email"] = (req.email or "").strip().lower()
        except Exception:
            pass

        # Build magic link (host-aware)
        try:
            base = request.host_url.rstrip("/")
            magic_url = f"{base}/r/{token}"
        except Exception:
            magic_url = f"/r/{token}"

        current_app.logger.info("[MAGIC LINK] request_id=%s url=%s", req.id, magic_url)

        # Send magic link email (best effort)
        try:
            from mail_service import send_notification_email

            recipient = getattr(req, "email", None)
            if recipient:
                subject = "Вашият защитен линк за проследяване в HelpChain"
                context = {
                    "subject": subject,
                    # PII guard: no names/phones/emails in outbound email body
                    "content": f"Ето вашият защитен линк за проследяване:<br><a href='{magic_url}'>{magic_url}</a>",
                    "magic_url": magic_url,
                    "request_id": req.id,
                }
                send_notification_email(recipient, subject, "email_template.html", context)
        except ModuleNotFoundError:
            current_app.logger.info("[EMAIL] mail_service not configured; magic link email skipped (dev mode)")
        except Exception as e:
            current_app.logger.warning("[EMAIL] magic link send failed: %s", e)

        session.pop("request_draft", None)
        session["last_request_id"] = req.id

        category = draft.get("category")
        urgency = draft.get("urgency")
        is_emergency = (
            category in ("emergency", "urgent")
            or urgency in ("critical", "emergency", "urgent")
        )

        app = current_app._get_current_object()
        if is_emergency and hasattr(app, "can_send_emergency_email") and app.can_send_emergency_email():
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
    return render_template("success.html", request_id=request_id, is_admin=is_admin), 200


@main_bp.get("/pilot", endpoint="pilot")
def pilot_dashboard():
    now = utc_now()
    week_ago = now - timedelta(days=7)
    since_14d = now - timedelta(days=14)

    not_deleted = Request.deleted_at.is_(None)

    total_requests = db.session.query(func.count(Request.id)).filter(not_deleted).scalar() or 0

    open_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.notin_(["done", "rejected"])
    ).scalar() or 0

    closed_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.in_(["done", "rejected"])
    ).scalar() or 0

    closed_last_7d = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.completed_at.isnot(None),
        Request.completed_at >= week_ago
    ).scalar() or 0

    avg_resolution_hours = db.session.query(
        func.avg(func.julianday(Request.completed_at) - func.julianday(Request.created_at)) * 24.0
    ).filter(
        not_deleted,
        Request.completed_at.isnot(None),
        Request.created_at.isnot(None)
    ).scalar()
    avg_resolution_hours = float(avg_resolution_hours) if avg_resolution_hours is not None else None

    unassigned_48h = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.notin_(["done", "rejected"]),
        Request.owner_id.is_(None),
        Request.created_at <= (now - timedelta(days=2))
    ).scalar() or 0

    stale_7d = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.notin_(["done", "rejected"]),
        Request.created_at <= (now - timedelta(days=7))
    ).scalar() or 0

    high_open = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.notin_(["done", "rejected"]),
        Request.priority == "high"
    ).scalar() or 0

    status_rows = (
        db.session.query(Request.status, func.count(Request.id))
        .filter(not_deleted)
        .group_by(Request.status)
        .order_by(func.count(Request.id).desc())
        .all()
    )
    status_labels = [r[0] or "unknown" for r in status_rows]
    status_counts = [int(r[1]) for r in status_rows]

    cat_rows = (
        db.session.query(Request.category, func.count(Request.id))
        .filter(not_deleted)
        .group_by(Request.category)
        .order_by(func.count(Request.id).desc())
        .all()
    )
    cat_labels = [r[0] or "unknown" for r in cat_rows]
    cat_counts = [int(r[1]) for r in cat_rows]

    trend_rows = (
        db.session.query(func.date(Request.created_at), func.count(Request.id))
        .filter(not_deleted, Request.created_at >= since_14d)
        .group_by(func.date(Request.created_at))
        .order_by(func.date(Request.created_at))
        .all()
    )
    trend_dates = [str(r[0]) for r in trend_rows]
    trend_counts = [int(r[1]) for r in trend_rows]

    total_volunteers = db.session.query(func.count(Volunteer.id)).filter(
        Volunteer.is_active.is_(True)
    ).scalar() or 0
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
    not_deleted = Request.deleted_at.is_(None)

    total_requests = db.session.query(func.count(Request.id)).filter(not_deleted).scalar() or 0
    open_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.notin_(["done", "rejected"])
    ).scalar() or 0
    helped_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status == "done"
    ).scalar() or 0
    closed_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.in_(["done", "rejected"])
    ).scalar() or 0
    total_volunteers = db.session.query(func.count(Volunteer.id)).filter(
        Volunteer.is_active.is_(True)
    ).scalar() or 0
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
    not_deleted = Request.deleted_at.is_(None)

    helped_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status == "done"
    ).scalar() or 0

    closed_requests = db.session.query(func.count(Request.id)).filter(
        not_deleted,
        Request.status.in_(["done", "rejected"])
    ).scalar() or 0

    active_volunteers = db.session.query(func.count(Volunteer.id)).filter(
        Volunteer.is_active.is_(True)
    ).scalar() or 0

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


@main_bp.route("/success_stories")
def success_stories():
    return render_template("success_stories.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.get("/video-chat")
def video_chat():
    return render_template("video_chat.html")


@main_bp.post("/set-language")
@main_bp.post("/set_language")
def set_language():
    supported = {"bg", "fr", "en"}
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
        title_bg = (
            data.get("content", {})
                .get("title", {})
                .get("bg")
        )
        icon = data.get("ui", {}).get("icon") or "fa-solid fa-circle-question text-secondary"
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

    # Volunteers query (SAFE)
    volunteers = []
    no_volunteers = True
    db_error = None

    try:
        # Търсим по canonical (и по оригиналния slug като резервен)
        # + по display name, ако някой е въвел "Храна" в skills.
        patterns = [
            f"%{canonical}%",
            f"%{category}%",
            f"%{category_info['name']}%",
        ]

        # махаме дубликати/празни
        patterns = [p for p in dict.fromkeys(patterns) if p and p != "%%"]

        filters = [Volunteer.skills.ilike(p) for p in patterns]

        # ако нямаме никакви patterns, просто не удряме DB с безсмислена заявка
        if filters:
            volunteers = Volunteer.query.filter(or_(*filters)).all()
        else:
            volunteers = []

        no_volunteers = (len(volunteers) == 0)

    except Exception as e:
        # НЕ чупим страницата на production
        current_app.logger.exception("category_help: Volunteer query failed")
        db_error = str(e)
        volunteers = []
        no_volunteers = True

    is_admin = bool(session.get("admin_logged_in", False))

    # По желание: можеш да покажеш db_error само в debug (не в production UI)
    return render_template(
        "category_help.html",
        category=canonical,                 # важно: canonical, не raw
        category_display=category_display,  # ако още го ползваш някъде
        category_info=category_info,
        volunteers=volunteers,
        no_volunteers=no_volunteers,
        is_admin=is_admin,
        # debug_db_error=db_error if current_app.debug else None,
    )


@main_bp.get("/sw.js")
def service_worker():
    # Serve /sw.js from src/static/sw.js
    return send_from_directory(current_app.static_folder, "sw.js")
