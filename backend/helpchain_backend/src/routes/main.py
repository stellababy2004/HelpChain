from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
)

from ..extensions import limiter
from ..models import Request, Volunteer, db
from ..category_data import CATEGORIES, ALIASES, COMMON
from sqlalchemy import or_

main_bp = Blueprint("main", __name__)


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

    return {"url_lang": url_lang, "safe_url_for": safe_url_for}


@main_bp.route("/", methods=["GET"])
def index():
    """Главна страница"""
    return render_template("home_new.html"), 200


@main_bp.route("/categories", methods=["GET"])
def categories():
    """Списък с всички категории"""
    items = []
    for key, value in CATEGORIES.items():
        items.append(
            {
                "slug": key,
                "name": value["content"]["title"]["bg"],
                "description": value["content"]["intro"]["bg"],
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

        try:
            req = Request(
                title=title,
                description=description,
                name=name,
                phone=phone or None,
                email=email or None,
                location_text=location_text or None,
                status="pending",
                priority=priority,
                category=category,
            )

            current_app.logger.warning(
                "About to INSERT: title=%r name=%r phone=%r email=%r category=%r priority=%r",
                title, name, phone, email, category, priority
            )

            db.session.add(req)
            db.session.commit()

            current_app.logger.warning("INSERT OK id=%s", req.id)

            # Optional emergency triggers (ако ги имаш)
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

            flash("Заявката е изпратена успешно.", "success")
            return redirect(url_for("main.index"))

        except Exception as e:
            current_app.logger.exception("SUBMIT_REQUEST FAILED: %s", e)
            db.session.rollback()
            flash(f"Грешка при подаване на заявката: {str(e)}", "error")
            return redirect(url_for("main.submit_request"))

    return render_template("submit_request.html")


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


@main_bp.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form.get("language", "bg")
    resp = redirect(request.referrer or url_for("main.index"))
    resp.set_cookie("language", lang, max_age=30 * 24 * 3600)
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
