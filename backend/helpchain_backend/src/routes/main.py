from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..models import Request, Volunteer, db

main_bp = Blueprint("main", __name__)


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
            "home_new.html",
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
            return redirect(url_for("main.index"))
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
            return redirect(url_for("main.index"))
        except Exception as e:
            flash(f"Грешка при записване като доброволец: {str(e)}", "error")

    return render_template("become_volunteer.html")


@main_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    """Обратна връзка"""
    if request.method == "POST":
        # Обработка на feedback
        flash("Благодарим ви за обратната връзка!", "success")
        return redirect(url_for("main.about"))

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
