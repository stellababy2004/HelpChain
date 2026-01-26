import re

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
from flask_babel import get_locale as babel_get_locale
from datetime import datetime, timedelta

from ..extensions import limiter
from ..models import Request, Volunteer, db, utc_now
from ..category_data import CATEGORIES, ALIASES, COMMON
from sqlalchemy import or_, func

# Supported countries for MVP KPI (keep simple; can be moved to config later)
COUNTRIES_SUPPORTED = ("FR", "CH", "CA")

ALLOWED_CATEGORIES = {"health", "administrative", "psychological", "legal", "housing", "other"}
ALLOWED_URGENCY = {"low", "medium", "high"}

main_bp = Blueprint("main", __name__)


# --- helpers ---

def _clean(val: str) -> str:
    return (val or "").strip()


def _collapse_spaces(value: str) -> str:
    return " ".join(value.split())


def _normalize_city(city: str | None) -> str | None:
    if not city:
        return None
    city = re.sub(r"\s+", " ", city.strip())

    def smart_title(word: str) -> str:
        if "-" in word:
            return "-".join(smart_title(w) for w in word.split("-"))
        if "'" in word:
            return "'".join(smart_title(w) for w in word.split("'"))
        return word.capitalize()

    return " ".join(smart_title(w) for w in city.split())


def _normalize_name(name):
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip())


def _normalize_email(value: str | None) -> str | None:
    value = _clean(value)
    if not value:
        return None
    normalized = re.sub(r"\s+", "", value).strip().lower()
    return normalized or None


def _normalize_phone(value: str | None) -> str | None:
    value = _clean(value)
    if not value:
        return None
    normalized = value.strip()
    normalized = re.sub(r"[^\d+]", "", normalized)
    if normalized.startswith("00"):
        normalized = "+" + normalized[2:]
    if normalized.count("+") > 1:
        normalized = normalized.replace("+", "")
        normalized = "+" + normalized
    return normalized or None


CATEGORY_LABELS = {
    "health": "Health",
    "administrative": "Administrative",
    "psychological": "Psychological",
    "legal": "Legal",
    "housing": "Housing",
    "other": "Other",
}


def _priority_from_urgency(urgency: str | None) -> str:
    u = (_clean(urgency) or "").lower()
    if u in {"high", "urgent"}:
        return "high"
    if u in {"medium"}:
        return "medium"
    return "low"


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
    return render_template("volunteer_login.html"), 200


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
def submit_request():
    if request.method == "GET":
        draft = session.get("request_draft") or {}
        return render_template("submit_request.html", draft=draft)

    category = _clean(request.form.get("category"))
    description = _clean(request.form.get("description"))
    urgency = _clean(request.form.get("urgency"))
    raw_city = _clean(request.form.get("city"))
    city = _normalize_city(raw_city)
    postal_code = _clean(request.form.get("postal_code"))
    contact_method = _clean(request.form.get("contact_method"))
    raw_name = _clean(request.form.get("name"))
    name = _normalize_name(raw_name)
    email = _normalize_email(request.form.get("email"))
    phone = _normalize_phone(request.form.get("phone"))

    errors = []

    if category not in ALLOWED_CATEGORIES:
        errors.append("Моля изберете валиден тип помощ.")
    if not (30 <= len(description) <= 800):
        errors.append("Описанието трябва да е между 30 и 800 знака.")
    if urgency not in ALLOWED_URGENCY:
        errors.append("Моля изберете валидна спешност.")
    if not city:
        errors.append("Градът е задължителен.")
    if contact_method not in {"email", "phone"}:
        errors.append("Моля изберете начин за контакт (email или phone).")
    else:
        if contact_method == "email" and not email:
            errors.append("Email е задължителен.")
        if contact_method == "phone" and not phone:
            errors.append("Телефон е задължителен.")

    if errors:
        for e in errors:
            flash(e, "danger")
        draft = {
            "category": category,
            "description": description,
            "urgency": urgency,
            "city": city,
            "name": name,
            "region": postal_code or None,
            "priority": {"low": 1, "medium": 2, "high": 3}.get(urgency, 2),
            "email": email or None,
            "phone": phone or None,
            # title derived at confirm time
            "location_text": f"{city}{(' ' + postal_code) if postal_code else ''}",
            "source_channel": "web",
            "contact_method": contact_method,
        }
        return render_template("submit_request.html", draft=draft), 400

    session["request_draft"] = {
        "category": category,
        "description": description,
        "urgency": urgency,
        "city": city,
        "postal_code": postal_code,
        "region": postal_code or None,
        "priority": {"low": 1, "medium": 2, "high": 3}[urgency],
        "name": name,
        "email": email or None,
        "phone": phone or None,
        "location_text": f"{city}{(' ' + postal_code) if postal_code else ''}",
        "source_channel": "web",
        "contact_method": contact_method,
    }

    return redirect(url_for("main.submit_request_confirm"))



@main_bp.route("/submit_request/confirm", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def submit_request_confirm():
    draft = session.get("request_draft")
    if not draft:
        flash("Сесията изтече. Моля, подай заявката отново.", "error")
        return redirect(url_for("main.submit_request"))

    if request.method == "GET":
        return render_template("request_preview.html", draft=draft)

    try:
        category_raw = _clean(draft.get("category"))
        category_value = category_raw.lower() if category_raw else "general"
        if not category_value:
            flash("Моля изберете валиден тип помощ.", "danger")
            return redirect(url_for("main.submit_request"))
        city_raw = draft.get("city")
        postal_code_raw = draft.get("postal_code") or draft.get("region")
        city = _normalize_city(_clean(city_raw))
        postal_code = _clean(postal_code_raw)
        raw_name = draft.get("name")
        name = _normalize_name(raw_name)
        description = _clean(draft.get("description"))
        email = _normalize_email(draft.get("email"))
        phone = _normalize_phone(draft.get("phone"))
        urgency = _clean(draft.get("urgency"))
        priority = _priority_from_urgency(urgency)
        where = " ".join(p for p in (city, postal_code) if p)
        location_text = where or None
        pretty_cat = CATEGORY_LABELS.get(category_value, category_raw.capitalize() or "Request")
        title = f"{pretty_cat} • {where}" if where else pretty_cat

        new_req = Request(
            title=title,
            description=description or None,
            email=email or None,
            phone=phone or None,
            city=city or None,
            region=postal_code or None,
            location_text=location_text,
            status="pending",
            priority=priority,
            source_channel="web",
            category=category_value,
            name=name or None,
        )

        db.session.add(new_req)
        db.session.commit()

        session.pop("request_draft", None)

        tracking = f"HC-{new_req.created_at:%Y%m%d}-{new_req.id:05d}" if getattr(new_req, "created_at", None) else f"HC-{new_req.id:05d}"
        try:
            log_audit("request_created", request_id=new_req.id)
        except Exception:
            current_app.logger.info("audit log missing for request_created %s", new_req.id)

        return redirect(url_for("main.request_submitted", tracking=tracking))

    except Exception as exc:
        current_app.logger.exception("CONFIRM FAILED: %s", exc)
        db.session.rollback()
        flash("Грешка при записване. Моля, опитай отново.", "error")
        return redirect(url_for("main.submit_request"))


@main_bp.get("/success")
def success():
    request_id = request.args.get("request_id") or session.get("last_request_id")
    is_admin = bool(session.get("admin_logged_in"))
    return render_template("success.html", request_id=request_id, is_admin=is_admin), 200


@main_bp.route("/request_submitted")
def request_submitted():
    tracking = request.args.get("tracking")
    return render_template("request_submitted.html", tracking=tracking), 200


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
