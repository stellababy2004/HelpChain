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
)
from werkzeug.security import check_password_hash
from flask_babel import get_locale as babel_get_locale
from datetime import timedelta, datetime

from ..extensions import limiter
from ..models import Request, Volunteer, db, utc_now
from ..category_data import CATEGORIES, ALIASES, COMMON
from sqlalchemy import or_, func
from functools import wraps
from urllib.parse import urlparse, urljoin

COUNTRIES_SUPPORTED = ["FR", "CH", "CA", "BG"]

main_bp = Blueprint("main", __name__)


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


def is_request_matching_volunteer(request_obj, volunteer_obj):
    """v1 deterministic matching: status open + category match + location/remote."""
    if not request_obj or not volunteer_obj:
        return False

    if (getattr(request_obj, "status", "") or "").lower() != "open":
        return False

    # exclude assigned/archived/deleted
    if getattr(request_obj, "assigned_volunteer_id", None) is not None:
        return False
    if getattr(request_obj, "is_archived", False):
        return False
    if getattr(request_obj, "deleted_at", None) is not None:
        return False

    volunteer_skills = normalize_list(getattr(volunteer_obj, "skills", None))
    request_categories = normalize_list(getattr(request_obj, "category", None))

    if not (volunteer_skills & request_categories):
        return False

    if is_remote_request(request_obj):
        return True

    v_city = (getattr(volunteer_obj, "city", None) or getattr(volunteer_obj, "location", None) or "").strip().lower()
    r_city = (getattr(request_obj, "city", None) or "").strip().lower()
    if v_city and r_city:
        return v_city == r_city

    # strict: if city missing on either side and not remote, no match
    return False


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
    return render_template("home_new.html"), 200


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
def volunteer_login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Моля въведи имейл.", "warning")
            return render_template("volunteer_login.html", minimal_page=True), 200

        volunteer = Volunteer.query.filter(Volunteer.email.ilike(email)).first()

        if not volunteer or not getattr(volunteer, "is_active", True):
            flash("Грешен имейл или профилът не е активен.", "danger")
            return render_template("volunteer_login.html", minimal_page=True), 200

        session["volunteer_id"] = int(volunteer.id)
        session.permanent = True
        session["just_logged_in"] = True

        try:
            volunteer.last_activity = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()

        return redirect(
            get_safe_next(url_for("main.volunteer_dashboard")),
            code=303,
        )

    return render_template("volunteer_login.html", minimal_page=True), 200


@main_bp.post("/volunteer/logout")
def volunteer_logout():
    session.pop("volunteer_id", None)
    session.pop("just_logged_in", None)
    return redirect(url_for("main.index"), code=303)


@main_bp.route("/become_volunteer", methods=["GET", "POST"])
def become_volunteer():
    """Public landing + submission endpoint for new volunteers."""
    if request.method == "POST":
        # TODO: collect and persist the submitted volunteer data
        return redirect(url_for("main.volunteer_confirmation"))

    return render_template("become_volunteer.html"), 200


@main_bp.get("/volunteer/confirmation")
def volunteer_confirmation():
    """Confirmation screen after submitting volunteer interest."""
    return render_template("volunteer_confirmation.html"), 200


@main_bp.get("/volunteer/dashboard")
@require_volunteer_login
def volunteer_dashboard():
    volunteer = _current_volunteer()

    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

    just_logged_in = session.pop("just_logged_in", None)

    open_requests = Request.query.filter_by(status="open").all()
    matched_requests = [
        r for r in open_requests if is_request_matching_volunteer(r, volunteer)
    ]

    current_app.logger.info(
        "Matching check",
        extra={
            "volunteer_id": volunteer.id,
        "matched_requests": len(matched_requests),
    },
    )

    return render_template(
        "volunteer_dashboard.html",
        volunteer=volunteer,
        matches=matched_requests,
        just_logged_in=bool(just_logged_in),
    ), 200


@main_bp.route("/volunteer/profile", methods=["GET", "POST"])
@require_volunteer_login
def volunteer_profile():
    volunteer = _current_volunteer()

    if not volunteer:
        return redirect(url_for("main.volunteer_login", next=request.path))

    if request.method == "POST":
        for field in ("name", "email", "phone", "city", "skills", "notes", "availability"):
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
@limiter.limit("5 per minute; 30 per hour")
def submit_request():
    """Подаване на заявка за помощ"""
    if request.method == "POST":
        current_app.logger.warning("SUBMIT_REQUEST POST hit")
        current_app.logger.warning("Form keys=%s", list(request.form.keys()))
        current_app.logger.warning("website(honeypot)='%s'", (request.form.get("website") or "").strip())
        # Honeypot anti-bot field (ако се задейства, искам да го ВИДИШ)
        website = (request.form.get("website") or "").strip()
        if website:
            current_app.logger.warning("Honeypot triggered on submit_request: website=%r", website)
            flash("Формата беше отхвърлена (анти-бот). Опитай пак.", "error")
            return redirect(url_for("main.submit_request"))

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

    return render_template("submit_request.html")


@main_bp.post("/submit_request/confirm")
@limiter.limit("5 per minute")
def submit_request_confirm():
    draft = session.get("request_draft")
    if not draft:
        flash("Сесията изтече. Моля, подай заявката отново.", "error")
        return redirect(url_for("main.submit_request"))

    try:
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

        db.session.add(req)
        db.session.commit()

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

        return redirect(url_for("main.success", request_id=req.id))

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
