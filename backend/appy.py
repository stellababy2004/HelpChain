# -*- coding: utf-8 -*-
import os
import io
import csv
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
    make_response,
)
from werkzeug.exceptions import BadRequest
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_migrate import Migrate
from flask_babel import Babel, _
from flask_mail import Mail, Message

# Hugging Face client (по избор)
try:
    from huggingface_hub import InferenceClient
except Exception:  # noqa: BLE001
    InferenceClient = None

# Локални модули
from .models import db, Volunteer, HelpRequest, Feedback, User  # noqa: F401
from .forms import VolunteerForm  # noqa: F401

# ── ENV ──────────────────────────────────────────────────────────────────────
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# ── PATHS ────────────────────────────────────────────────────────────────────
BASEDIR = Path(__file__).resolve().parent  # backend/
PROJECT_ROOT = BASEDIR.parent.resolve()  # корен на проекта

# ── APP ──────────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "frontend" / "templates"),
    static_folder=str(PROJECT_ROOT / "frontend" / "static"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecretkey")
app.config["WTF_CSRF_ENABLED"] = True
app.logger.info("BOOT: SECRET_KEY len=%s", len(app.config.get("SECRET_KEY", "")))

# ── STORAGE / DB ─────────────────────────────────────────────────────────────
INSTANCE_DIR = BASEDIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

db_url = os.getenv("DATABASE_URL")
if db_url:
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{INSTANCE_DIR / 'volunteers.db'}"
    )
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

# ── I18N ─────────────────────────────────────────────────────────────────────
babel = Babel(app)


def get_locale() -> str:
    return request.args.get("lang") or request.cookies.get("language") or "bg"


babel.locale_selector_func = get_locale
app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(PROJECT_ROOT / "translations")

# ── MAIL ─────────────────────────────────────────────────────────────────────
# ⚠️ Вземай от .env; не дръж пароли в кода
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.zoho.eu")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "465"))
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "True") == "True"
app.config["MAIL_USE_TLS"] = (
    os.getenv("MAIL_USE_TLS", "False") == "True"
)  # ако си на 465/SSL, остави False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"]
)
mail = Mail(app)

# ── HF CLIENT (по избор) ─────────────────────────────────────────────────────
hf_model = os.getenv("HF_MODEL", "HuggingFaceH4/zephyr-7b-beta")
hf_client = InferenceClient(hf_model, token=HF_TOKEN) if HF_TOKEN else None

# ── UPLOADS ──────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── 400 handler: чисти счупена session/CSRF cookie ──────────────────────────
@app.errorhandler(BadRequest)
def handle_bad_request(e):  # noqa: ANN001
    try:
        # ако сесията е повредена/стара → изчисти
        # (няма нужда от current_user тук)
        pass
    except Exception:  # noqa: BLE001
        pass
    resp = redirect(request.url)
    resp.delete_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
    return resp


# ── CONTEXT ──────────────────────────────────────────────────────────────────
@app.context_processor
def inject_get_locale():
    return {"get_locale": get_locale}


# ── LOGIN MANAGER ────────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):  # noqa: ANN001
    return User.query.get(int(user_id))


# ── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    stats = {"total": 0, "open": 0, "closed": 0}
    recent = []
    return render_template("index.html", user=current_user, stats=stats, recent=recent)


# ---------- Admin Login ----------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == "admin" and password == "help2025!":
            # проста демо-сесия (не е за продукция)
            from flask import session as flask_session

            flask_session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Грешно потребителско име или парола!"
    return render_template("admin_login.html", error=error)


@app.route("/admin_dashboard")
def admin_dashboard():
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    requests_obj = {
        "items": [
            {"id": 1, "name": "Мария", "status": "Активен"},
            {"id": 2, "name": "Георги", "status": "Завършен"},
        ]
    }
    logs_dict = {
        1: [{"status": "Активен", "changed_at": "2025-07-22"}],
        2: [{"status": "Завършен", "changed_at": "2025-07-21"}],
    }
    return render_template(
        "admin_dashboard.html", requests=requests_obj, logs_dict=logs_dict
    )


# ---------- Volunteers ----------
@app.route("/admin_volunteers", methods=["GET", "POST"])
def admin_volunteers():
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteers = Volunteer.query.order_by(Volunteer.id.desc()).all()
    return render_template("admin_volunteers.html", volunteers=volunteers)


@app.route("/admin_volunteers/add", methods=["GET", "POST"])
def add_volunteer():
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        email = request.form["email"].strip()
        if Volunteer.query.filter_by(email=email).first():
            flash("Този имейл вече е регистриран!", "danger")
            return redirect(url_for("add_volunteer"))
        name = request.form["name"].strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        volunteer = Volunteer(name=name, email=email, phone=phone, location=location)
        db.session.add(volunteer)
        db.session.commit()
        flash(_("Доброволецът е добавен успешно!"), "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("add_volunteer.html")


@app.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
def edit_volunteer(id):  # noqa: A002, ANN001
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    if request.method == "POST":
        volunteer.name = request.form["name"].strip()
        volunteer.email = request.form["email"].strip()
        volunteer.phone = request.form.get("phone", "").strip()
        volunteer.location = request.form.get("location", "").strip()
        db.session.commit()
        flash("Промените са запазени!", "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("edit_volunteer.html", volunteer=volunteer)


@app.route("/delete_volunteer/<int:id>", methods=["POST"])
def delete_volunteer(id):  # noqa: A002, ANN001
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    db.session.delete(volunteer)
    db.session.commit()
    flash("Доброволецът е изтрит успешно!", "success")
    return redirect(url_for("admin_volunteers"))


@app.route("/export_volunteers")
def export_volunteers():
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Име", "Имейл", "Телефон", "Град/регион"])
    for v in Volunteer.query.order_by(Volunteer.id.asc()).all():
        writer.writerow([v.id, v.name, v.email, v.phone, v.location])
    output = "\ufeff" + si.getvalue()  # BOM за Excel
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=volunteers.csv"},
    )


# ---------- Help Requests ----------
@app.route("/submit_request", methods=["GET", "POST"])
def submit_request():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        description = request.form.get("description", "").strip()
        message = request.form.get("message", "").strip()
        help_request = HelpRequest(
            title=title,
            name=full_name,
            email=email,
            phone=phone,
            description=description,
            message=message,
        )
        db.session.add(help_request)
        db.session.commit()
        flash("Вашата заявка беше успешно изпратена.", "success")
        return redirect(url_for("index"))
    return render_template("help_request.html")


@app.route("/admin_requests")
def admin_requests():
    from flask import session as flask_session

    if not flask_session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    requests_q = HelpRequest.query.order_by(HelpRequest.timestamp.desc()).all()
    return render_template("admin_requests.html", requests=requests_q)


# ---------- Content pages ----------
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/success_stories")
def success_stories():
    return render_template("success_stories.html")


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        fb = Feedback(
            name=request.form["name"],
            email=request.form["email"],
            message=request.form["message"],
        )
        db.session.add(fb)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("feedback.html")


# ---------- Language ----------
@app.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form.get("language", "bg")
    resp = make_response(redirect(request.referrer or url_for("index")))
    resp.set_cookie("language", lang)
    return resp


# ---------- Volunteer public form ----------
@app.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    form = VolunteerForm()
    if form.validate_on_submit():
        if Volunteer.query.filter_by(email=form.email.data.strip()).first():
            flash("Този имейл вече е регистриран!", "danger")
            return redirect(url_for("volunteer_register"))
        volunteer = Volunteer(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            phone=form.phone.data.strip(),
            location=form.location.data.strip(),
        )
        db.session.add(volunteer)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("volunteer_register.html", form=form)


# ---------- Simple chatbot API ----------
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").lower()
    lang = data.get("lang", "bg")

    def answers_en(msg: str) -> str:
        if "volunteer" in msg:
            return "To become a volunteer, fill in the registration form and our team will contact you!"
        if "team" in msg or "contact" in msg:
            return "You can contact our team via the contact form on the site or at info@helpchain.bg."
        if "request" in msg or "help" in msg:
            return "To submit a help request, click the 'Submit Help Request' button and fill in the form."
        if "platform" in msg:
            return "HelpChain is a platform connecting people in need with volunteers ready to help."
        if "security" in msg:
            return "All your data is processed confidentially and used only for the purpose of helping."
        return "HelpChain Assistant: I can help with questions about the platform, volunteers, and help requests!"

    def answers_fr(msg: str) -> str:
        if "bénévole" in msg:
            return "Pour devenir bénévole, remplissez le formulaire d'inscription et notre équipe vous contactera !"
        if "équipe" in msg or "contact" in msg:
            return "Vous pouvez contacter notre équipe via le formulaire de contact sur le site ou à info@helpchain.bg."
        if "demande" in msg or "aide" in msg:
            return "Pour soumettre une demande d'aide, cliquez sur le bouton 'Soumettre une demande d'aide' et remplissez le formulaire."
        if "plateforme" in msg:
            return "HelpChain est une plateforme qui met en relation les personnes dans le besoin avec des bénévoles prêts à aider."
        if "sécurité" in msg:
            return "Toutes vos données sont traitées de manière confidentielle et utilisées uniquement dans le but d'aider."
        return "HelpChain Assistant : Je peux vous aider avec des questions sur la plateforme, les bénévoles et les demandes d'aide !"

    def answers_bg(msg: str) -> str:
        if "доброволец" in msg:
            return "За да станеш доброволец, попълни формата за регистрация и наш екип ще се свърже с теб!"
        if "екип" in msg or "контакт" in msg:
            return "Можеш да се свържеш с екипа ни чрез контактната форма на сайта или на имейл info@helpchain.bg."
        if "заявка" in msg or "сигнал" in msg:
            return "За да подадеш заявка за помощ, натисни бутона 'Подай сигнал за помощ' и попълни формуляра."
        if "какво представлява" in msg or "платформа" in msg:
            return "HelpChain е платформа, която свързва хора в нужда с доброволци, готови да помогнат."
        if "сигурност" in msg:
            return "Всички твои данни се обработват поверително и се използват само за целите на помощта."
        return "HelpChain Assistant: Мога да помогна с въпроси за платформата, доброволци и заявки за помощ!"

    if HF_TOKEN and InferenceClient:
        # тук можеш да извикаш реалния модел; оставяме простите отговори за стабилност
        pass

    if lang == "en":
        answer = answers_en(user_message)
    elif lang == "fr":
        answer = answers_fr(user_message)
    else:
        answer = answers_bg(user_message)

    return jsonify({"answer": answer})


# ---------- Mail test ----------
@app.route("/test_mail")
def test_mail():
    sender = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")
    msg = Message(
        subject="Тест Zoho",
        recipients=[sender],
        body="Това е тестово съобщение от Flask-Mail и Zoho!",
    )
    mail.send(msg)
    return "Имейлът е изпратен успешно!"


# ---------- Search volunteers ----------
@app.route("/search_volunteers")
def search_volunteers():
    q = request.args.get("q", "").strip()
    if not q:
        vols = Volunteer.query.order_by(Volunteer.id.desc()).all()
    else:
        vols = (
            Volunteer.query.filter(
                (Volunteer.name.contains(q))
                | (Volunteer.email.contains(q))
                | (Volunteer.phone.contains(q))
            )
            .order_by(Volunteer.id.desc())
            .all()
        )
    return render_template("admin_volunteers.html", volunteers=vols)


# ---------- Stories ----------
@app.route("/stories")
def stories():
    return render_template("stories.html")


# ---------- Search ----------
@app.route("/search")
def search():
    query = request.args.get("q", "")
    if query:
        requests_q = HelpRequest.query.filter(
            HelpRequest.name.contains(query) | HelpRequest.message.contains(query)
        ).all()
        volunteers = Volunteer.query.filter(
            Volunteer.name.contains(query) | Volunteer.email.contains(query)
        ).all()
    else:
        requests_q = []
        volunteers = []
    return render_template(
        "search.html", requests=requests_q, volunteers=volunteers, query=query
    )


# ---------- Register ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username") or ""
        email = request.form.get("email") or ""
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Попълни имейл и парола", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Имейлът вече е регистриран", "warning")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password=hashed,
            role="volunteer",
            created_at=datetime.now(timezone.utc),
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash("Регистрацията е успешна. Влез с данните си.", "success")
            return redirect(url_for("login"))
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            app.logger.exception("register error: %s", exc)
            flash("Грешка при регистрацията. Опитай по-късно.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Попълни имейл и парола", "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Влязохте успешно", "success")
            return redirect(url_for("index"))

        flash("Грешен имейл или парола", "warning")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# Авто-миграции при старт (ако имаш помощна функция)
with app.app_context():
    al_upgrade = globals().get("_al_upgrade")
    if callable(al_upgrade):
        try:
            al_upgrade()
            app.logger.info("DB auto-upgrade: OK")
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("DB auto-upgrade skipped: %s", exc)
    else:
        app.logger.info("DB auto-upgrade: _al_upgrade not present, skipping")

# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
