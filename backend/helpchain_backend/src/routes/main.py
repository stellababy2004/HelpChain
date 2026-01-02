

from flask import Blueprint

main_bp = Blueprint("main", __name__)


@main_bp.get("/request")
def request_category():
    from flask import request, render_template, current_app
    from ..category_data import CATEGORIES, ALIASES, COMMON
    slug = request.args.get("category")
    canonical = ALIASES.get(slug, slug) if slug else None
    category = CATEGORIES.get(canonical) if canonical else None
    if not category:
        return render_template(
            "request_category.html",
            category=None,
            COMMON=COMMON,
            not_found=True,
            requested_slug=slug,
        ), 404
    # Покажи 112 ако severity е critical
    show_emergency = category["ui"].get("severity") == "critical"
    return render_template(
        "request_category.html",
        category=category,
        COMMON=COMMON,
        show_emergency=show_emergency,
        emergency_number=COMMON.get("emergency_number"),
        requested_slug=slug,
    )

    # MVP: логване на заявката (може да се замени с база/имейл)
    current_app.logger.info(f"New help request: category={canonical}, desc={description}, contact={contact}, city={city}")

    # TODO: save to DB, send email, etc.
    flash("Заявката е изпратена успешно! Ще се свържем с вас при първа възможност.", "success")
    return redirect(url_for("main.request_category", category=canonical))
@main_bp.route("/request/form", methods=["GET"])
def request_form():
    slug = request.args.get("category")
    if not slug:
        return redirect(url_lang("main.categories_index"))
    from ..category_data import CATEGORIES, ALIASES, COMMON
    canonical = ALIASES.get(slug, slug)
    category = CATEGORIES.get(canonical)
    if not category:
        current_app.logger.warning(f"Invalid category slug for form: {slug}")
        return redirect(url_lang("main.categories_index"))
    # Тук ще се използва универсален template за формата (request_form.html)
    return render_template(
        "request_form.html",
        category=category,
        COMMON=COMMON
    )



from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app
from ..models import Request, Volunteer, db
from ..category_data import CATEGORIES, ALIASES, COMMON, CATEGORIES_SCHEMA_VERSION
main_bp = Blueprint("main", __name__)

# Временен тестов handler за /request
@main_bp.get("/request")
def request_category():
    return "OK /request"


@main_bp.route("/")
def index():
    """Начална страница – unified към нов шаблон `home_new.html`."""
    try:
        volunteers_count = Volunteer.query.count()
        requests_count = Request.query.count()
    except Exception:
        volunteers_count = requests_count = 0

    # Open requests count се пази ако решим да го покажем по-късно
    try:
        open_requests = Request.query.filter(Request.status != "completed").count()
    except Exception:
        open_requests = 0

    from flask import make_response, render_template

    resp = make_response(
        render_template(
            "index.html",
            volunteers_count=volunteers_count,
            requests_count=requests_count,
            open_requests=open_requests,
        )
    )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@main_bp.route("/about")
def about():
    """За нас страница"""
    return render_template("about.html")


@main_bp.route("/submit_request", methods=["GET", "POST"])
def submit_request():
    """Подаване на заявка за помощ"""
    if request.method == "POST":
        try:
            req = Request(
                name=request.form.get("name"),
                phone=request.form.get("phone"),
                email=request.form.get("email"),
                location=request.form.get("location"),
                category=request.form.get("category"),
                description=request.form.get("problem"),
                urgency=request.form.get("urgency", "normal"),
                status="pending",
            )
            db.session.add(req)
            db.session.commit()
            flash(
                "Благодарим ви че се свързахте с екипа ни! Ще се свържем с вас скоро.",
                "success",
            )
            return redirect(url_lang("main.index"))
        except Exception as e:
            flash(f"Грешка при подаване на заявката: {str(e)}", "error")

    return render_template("submit_request.html")


@main_bp.route("/become_volunteer", methods=["GET", "POST"])
def become_volunteer():
    """Регистрация на доброволец"""
    if request.method == "POST":
        try:
            volunteer = Volunteer(
                name=request.form.get("name"),
                email=request.form.get("email"),
                phone=request.form.get("phone"),
                skills=request.form.get("skills"),
                location=request.form.get("location"),
            )
            db.session.add(volunteer)
            db.session.commit()
            flash(
                "Благодарим ви че се записахте като доброволец! Ще се свържем с вас скоро.",
                "success",
            )
            return redirect(url_lang("main.index"))
        except Exception as e:
            flash(f"Грешка при записване като доброволец: {str(e)}", "error")

    return render_template("become_volunteer.html")


@main_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    """Обратна връзка"""
    if request.method == "POST":
        # Обработка на feedback
        flash("Благодарим ви за обратната връзка!", "success")
        return redirect(url_lang("main.about"))

    return render_template("feedback.html")


@main_bp.route("/faq")
def faq():
    """Често задавани въпроси"""
    return render_template("faq.html")


@main_bp.route("/success_stories")
def success_stories():
    """Успешни истории"""
    return render_template("success_stories.html")


@main_bp.route("/privacy")
def privacy():
    """Политика за поверителност"""
    return render_template("privacy.html")


@main_bp.route("/terms")
def terms():
    """Общи условия"""
    return render_template("terms.html")


@main_bp.route("/set_language", methods=["POST"])
def set_language():
    """Смяна на език"""
    lang = request.form.get("language", "bg")
    resp = redirect(request.referrer or url_for("main.index"))
    resp.set_cookie("language", lang, max_age=30 * 24 * 3600)
    return resp


@main_bp.route("/category_help/<category>")
def category_help(category):
    """Показва доброволци в дадена категория"""
    # Дефинираме mapping на категориите
    category_names = {
        "food": "Храна",
        "medical": "Медицинска помощ",
        "transport": "Транспорт",
        "other": "Друго",
    }

    category_display = category_names.get(category, category.title())

    # Филтрираме доброволци които имат тази категория в skills
    # Предполагаме че skills съдържа категории разделени със запетаи или като текст
    volunteers = Volunteer.query.filter(Volunteer.skills.ilike(f"%{category}%")).all()

    # Ако няма доброволци, показваме съобщение
    no_volunteers = len(volunteers) == 0

    # Проверяваме дали потребителят е администратор
    is_admin = session.get("admin_logged_in", False)

    return render_template(
        "category_help.html",
        category=category,
        category_display=category_display,
        volunteers=volunteers,
        no_volunteers=no_volunteers,
        is_admin=is_admin,
    )
