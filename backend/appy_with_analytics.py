# backend/appy.py
from __future__ import annotations

import csv
import json
import os
import secrets
from collections import Counter
from datetime import UTC, datetime, timedelta
from functools import wraps
from io import BytesIO, StringIO
from pathlib import Path

# 2FA библиотеки
import pyotp  # За TOTP (Time-based One-Time Password)
import qrcode  # За QR кодове
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import Babel, _
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Mail, Message
from flask_migrate import Migrate
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

# -----------------------------------------------------------------------------
# .env (зарежда се от backend директорията)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # .../backend
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# -----------------------------------------------------------------------------
# Flask app
# -----------------------------------------------------------------------------
INSTANCE_DIR = Path(__file__).resolve().parent / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["WTF_CSRF_ENABLED"] = True

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
db_url = os.getenv("DATABASE_URL")
if db_url:
    # Heroku-style -> SQLAlchemy
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{INSTANCE_DIR / 'volunteers.db'}"
    )
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

try:
    from .models import (
        AdminLog,
        AdminRole,
        # TwoFactorAuth,  # unused — премахнато
        # AdminSession,   # unused — премахнато
        AdminUser,
        Feedback,
        HelpRequest,
        SuccessStory,
        User,
        Volunteer,
        db,
    )  # type: ignore
except ImportError:
    from .models import (
        AdminLog,
        AdminRole,
        AdminUser,
        Feedback,
        HelpRequest,
        SuccessStory,
        User,
        Volunteer,
        db,
    )  # type: ignore

db.init_app(app)
migrate = Migrate(app, db)

# -----------------------------------------------------------------------------
# I18N / Babel
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(PROJECT_ROOT / "translations")

babel = Babel(app)


def get_locale():
    return request.args.get("lang") or request.cookies.get("language") or "bg"


# Flask-Babel v3
babel.locale_selector_func = get_locale


# -----------------------------------------------------------------------------
# Jinja2 filters
# -----------------------------------------------------------------------------
@app.template_filter("from_json")
def from_json_filter(s):
    """Филтър за парсене на JSON string в темплейти"""
    if not s:
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


@app.context_processor
def inject_get_locale():
    return {"get_locale": get_locale}


# -----------------------------------------------------------------------------
# Mail (Zoho)
# -----------------------------------------------------------------------------
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.zoho.eu")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "465"))
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "True") == "True"
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "False") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"]
)
mail = Mail(app)

# -----------------------------------------------------------------------------
# Uploads
# -----------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------
@app.errorhandler(BadRequest)
def handle_bad_request(e):
    # Ако сесията е корумпирана → изтрий сесийната бисквитка и рефрешни
    resp = redirect(request.url)
    resp.delete_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
    return resp


# -----------------------------------------------------------------------------
# Login manager
# -----------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def admin_required() -> bool:
    """Лесна проверка за админ сесия (прост вариант).
    Може да се замени с Flask-Login роля при нужда.
    """
    return bool(session.get("admin_logged_in"))


# -----------------------------------------------------------------------------
# Система за роли и сигурност
# -----------------------------------------------------------------------------


def get_current_admin_user():
    """Връща текущия административен потребител ако е логнат"""
    admin_username = session.get("admin_username")
    if admin_username:
        return AdminUser.query.filter_by(username=admin_username).first()
    return None


def require_role(required_role):
    """Декоратор за проверка на роля"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            admin_user = get_current_admin_user()
            if not admin_user:
                flash("Нужен е административен достъп.", "error")
                return redirect(url_for("admin_login"))

            if not admin_user.has_role(required_role):
                flash("Нямате необходимите права за това действие.", "error")
                return redirect(url_for("admin_dashboard"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def log_admin_action(action, details=None, entity_type=None, entity_id=None):
    """Записва административно действие в лога"""
    admin_user = get_current_admin_user()
    if not admin_user:
        return

    log_entry = AdminLog(
        admin_user_id=admin_user.id,
        action=action,
        details=json.dumps(details) if details else None,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        timestamp=datetime.utcnow(),
    )

    db.session.add(log_entry)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Грешка при записване на лог: {e}")


def create_admin_user(username, email, password, role=AdminRole.MODERATOR):
    """Създава нов административен потребител"""
    existing_user = AdminUser.query.filter(
        (AdminUser.username == username) | (AdminUser.email == email)
    ).first()

    if existing_user:
        return None, "Потребител с това име или email вече съществува"

    admin_user = AdminUser(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        created_at=datetime.utcnow(),
    )

    db.session.add(admin_user)
    try:
        db.session.commit()
        log_admin_action(
            "create_admin_user",
            {"new_user": username, "role": role.value},
            "admin_user",
            admin_user.id,
        )
        return admin_user, None
    except Exception as e:
        db.session.rollback()
        return None, f"Грешка при създаване на потребител: {e}"


# -----------------------------------------------------------------------------
# 2FA функционалности
# -----------------------------------------------------------------------------


def generate_totp_secret():
    """Генерира TOTP secret ключ"""
    return pyotp.random_base32()


def generate_backup_codes(count=10):
    """Генерира backup кодове за 2FA"""
    codes = []
    for _i in range(count):
        code = "".join(secrets.choice("0123456789") for j in range(8))
        codes.append(f"{code[:4]}-{code[4:]}")
    return codes


def generate_qr_code(admin_user):
    """Генерира QR код за настройка на 2FA"""
    if not admin_user.totp_secret:
        return None

    totp_uri = pyotp.totp.TOTP(admin_user.totp_secret).provisioning_uri(
        name=admin_user.email, issuer_name="HelpChain.bg Admin"
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертиране в base64 за показване в HTML
    import base64

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def verify_totp_token(admin_user, token):
    """Проверява TOTP токен"""
    if not admin_user.totp_secret:
        return False

    totp = pyotp.TOTP(admin_user.totp_secret)
    return totp.verify(token, valid_window=1)  # Позволява 30 сек толеранс


def verify_backup_code(admin_user, code):
    """Проверява backup код и го премахва при използване"""
    if not admin_user.backup_codes:
        return False

    try:
        backup_codes = json.loads(admin_user.backup_codes)
        if code in backup_codes:
            backup_codes.remove(code)
            admin_user.backup_codes = json.dumps(backup_codes)
            db.session.commit()
            return True
    except (json.JSONDecodeError, ValueError):
        pass

    return False


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        help_request = HelpRequest(name=name, email=email, phone=phone, message=message)
        db.session.add(help_request)
        db.session.commit()
        msg = Message(
            "New Help Request",
            sender="contact@helpchain.live",
            recipients=["admin@helpchain.live"],
        )
        msg.body = f"Name: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}"
        mail.send(msg)
        return redirect(url_for("index"))

    # Текущ потребител (ако е логнат)
    user = current_user if current_user.is_authenticated else None

    return render_template("index.html", user=user)


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        totp_token = request.form.get("totp_token", "")

        # Първо опитваме с новата система
        admin_user = AdminUser.query.filter_by(username=username).first()

        if admin_user and check_password_hash(admin_user.password_hash, password):
            # Нова система - проверяваме за заключване
            if admin_user.locked_until and admin_user.locked_until > datetime.utcnow():
                error = "Акаунтът е временно заключен. Опитайте отново по-късно."
            elif not admin_user.is_active:
                error = "Акаунтът е деактивиран."
            else:
                # Проверяваме дали е активирана 2FA
                if admin_user.two_factor_enabled:
                    if not totp_token:
                        # Трябва да въведе 2FA код
                        return render_template(
                            "admin_login.html",
                            error=None,
                            username=username,
                            password=password,
                            require_2fa=True,
                        )
                    elif not verify_totp_token(admin_user, totp_token):
                        error = "Невалиден код за двустепенна автентикация!"
                    else:
                        # Успешен логин с 2FA
                        admin_user.failed_login_attempts = 0
                        admin_user.last_login = datetime.utcnow()
                        db.session.commit()

                        session["admin_logged_in"] = True
                        session["admin_username"] = admin_user.username
                        session["admin_role"] = admin_user.role.value

                        log_admin_action("login_2fa", {"username": username})

                        flash(f"Добре дошли, {admin_user.username}!", "success")
                        return redirect(url_for("admin_dashboard"))
                else:
                    # Успешен логин без 2FA
                    admin_user.failed_login_attempts = 0
                    admin_user.last_login = datetime.utcnow()
                    db.session.commit()

                    session["admin_logged_in"] = True
                    session["admin_username"] = admin_user.username
                    session["admin_role"] = admin_user.role.value

                    log_admin_action("login", {"username": username})

                    flash(f"Добре дошли, {admin_user.username}!", "success")
                    return redirect(url_for("admin_dashboard"))
        else:
            # Фалбек към старата система (.env)
            load_dotenv(env_path, override=True)
            env_admin_user = os.getenv("ADMIN_USERNAME", "admin")
            env_admin_pass = os.getenv("ADMIN_PASSWORD", "")

            if username == env_admin_user and password == env_admin_pass:
                session["admin_logged_in"] = True
                session["admin_username"] = username
                session["admin_role"] = "super_admin"  # .env потребителят е super admin

                flash(f"Добре дошли, {username}! (legacy режим)", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                # Неуспешен логин - увеличаваме неуспешните опити за новата система
                if admin_user:
                    admin_user.failed_login_attempts += 1
                    if admin_user.failed_login_attempts >= 5:
                        admin_user.locked_until = datetime.utcnow() + timedelta(
                            minutes=30
                        )
                    db.session.commit()

                error = "Грешно потребителско име или парола!"

    return render_template("admin_login.html", error=error)


@app.route("/admin_logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Излезе от админ панела.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin_dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    status = request.args.get("status")
    volunteers = Volunteer.query.order_by(Volunteer.id.desc()).all()
    if status:
        requests_q = (
            HelpRequest.query.filter_by(status=status)
            .order_by(HelpRequest.timestamp.desc())
            .all()
        )
    else:
        requests_q = HelpRequest.query.order_by(HelpRequest.timestamp.desc()).all()

    latest_news = SuccessStory.query.order_by(SuccessStory.id.desc()).limit(10).all()

    # Статистика: доброволци по град/регион
    locations = [v.location for v in volunteers if getattr(v, "location", None)]
    location_stats = Counter(locations)

    return render_template(
        "admin_dashboard.html",
        volunteers=volunteers,
        requests=requests_q,
        latest_news=latest_news,
        location_stats=location_stats,
    )


@app.route("/admin_volunteers", methods=["GET", "POST"])
def admin_volunteers():
    if not admin_required():
        return redirect(url_for("admin_login"))
    volunteers = Volunteer.query.order_by(Volunteer.id.desc()).all()
    return render_template("admin_volunteers.html", volunteers=volunteers)


@app.route("/admin_volunteers/add", methods=["GET", "POST"])
def add_volunteer():
    if not admin_required():
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

        # Записваме в лога
        log_admin_action(
            action="added_volunteer",
            details={
                "volunteer_name": name,
                "volunteer_email": email,
                "volunteer_phone": phone,
                "volunteer_location": location,
            },
            entity_type="volunteer",
            entity_id=volunteer.id,
        )

        flash(_("Доброволецът е добавен успешно!"), "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("add_volunteer.html")


@app.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
def edit_volunteer(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    if request.method == "POST":
        # Запазваме старите стойности за лога
        old_data = {
            "name": volunteer.name,
            "email": volunteer.email,
            "phone": volunteer.phone,
            "location": volunteer.location,
        }

        volunteer.name = request.form["name"].strip()
        volunteer.email = request.form["email"].strip()
        volunteer.phone = request.form.get("phone", "").strip()
        volunteer.location = request.form.get("location", "").strip()
        db.session.commit()

        # Записваме в лога
        log_admin_action(
            action="edited_volunteer",
            details={
                "volunteer_id": id,
                "old_data": old_data,
                "new_data": {
                    "name": volunteer.name,
                    "email": volunteer.email,
                    "phone": volunteer.phone,
                    "location": volunteer.location,
                },
            },
            entity_type="volunteer",
            entity_id=id,
        )

        flash("Промените са запазени!", "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("edit_volunteer.html", volunteer=volunteer)


@app.route("/delete_volunteer/<int:id>", methods=["POST"])
def delete_volunteer(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)

    # Запазваме данните преди изтриване за лога
    volunteer_data = {
        "name": volunteer.name,
        "email": volunteer.email,
        "phone": volunteer.phone,
        "location": volunteer.location,
    }

    db.session.delete(volunteer)
    db.session.commit()

    # Записваме в лога
    log_admin_action(
        action="deleted_volunteer",
        details={"volunteer_id": id, "volunteer_data": volunteer_data},
        entity_type="volunteer",
        entity_id=id,
    )

    flash("Доброволецът е изтрит успешно!", "success")
    return redirect(url_for("admin_volunteers"))


@app.route("/export_volunteers")
def export_volunteers():
    if not admin_required():
        return redirect(url_for("admin_login"))
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Име", "Имейл", "Телефон", "Град/регион"])
    for v in Volunteer.query.order_by(Volunteer.id.asc()).all():
        writer.writerow([v.id, v.name, v.email, v.phone, v.location])
    output = "\ufeff" + si.getvalue()
    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=volunteers.csv"},
    )


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
    # увери се, че темплейтът съществува: backend/templates/submit_request.html
    return render_template("submit_request.html")


@app.route("/admin_requests")
def admin_requests():
    if not admin_required():
        return redirect(url_for("admin_login"))
    requests_q = HelpRequest.query.order_by(HelpRequest.timestamp.desc()).all()
    return render_template("admin_requests.html", requests=requests_q)


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


@app.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form.get("language", "bg")
    resp = make_response(redirect(request.referrer or url_for("index")))
    resp.set_cookie("language", lang)
    return resp


@app.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        if Volunteer.query.filter_by(email=email).first():
            flash("Този имейл вече е регистриран!", "danger")
            return redirect(url_for("volunteer_register"))
        volunteer = Volunteer(
            name=name,
            email=email,
            phone=phone,
            location=location,
        )
        db.session.add(volunteer)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("volunteer_register.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").lower()
    lang = data.get("lang", "bg")

    def answers_en(msg):
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

    def answers_fr(msg):
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

    def answers_bg(msg):
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

    if lang == "en":
        answer = answers_en(user_message)
    elif lang == "fr":
        answer = answers_fr(user_message)
    else:
        answer = answers_bg(user_message)

    return jsonify({"answer": answer})


@app.route("/test_mail")
def test_mail():
    sender = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")
    if not sender:
        return "MAIL_DEFAULT_SENDER/MAIL_USERNAME не са конфигурирани.", 500
    msg = Message(
        subject="Тест Zoho",
        recipients=[sender],
        body="Това е тестово съобщение от Flask-Mail и Zoho!",
    )
    mail.send(msg)
    return "Имейлът е изпратен успешно!"


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


@app.route("/stories")
def stories():
    return render_template("stories.html")


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


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
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
            created_at=datetime.now(UTC),
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash("Регистрацията е успешна. Влез с данните си.", "success")
            return redirect(url_for("login"))
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("register error: %s", exc)
            flash("Грешка при регистрацията. Опитай по-късно.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
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


@app.route("/volunteer_dashboard", methods=["GET", "POST"])
@login_required
def volunteer_dashboard():
    # Моите заявки
    my_requests = HelpRequest.query.filter_by(email=current_user.email).all()

    # Чужди заявки: Активни, които не са мои
    foreign_requests = HelpRequest.query.filter(
        HelpRequest.email != current_user.email, HelpRequest.status == "Активен"
    ).all()

    # Завършени мои
    finished_requests = HelpRequest.query.filter_by(
        email=current_user.email, status="Завършена"
    ).all()

    latest_news = SuccessStory.query.order_by(SuccessStory.id.desc()).limit(5).all()

    return render_template(
        "volunteer_dashboard.html",
        my_requests=my_requests,
        foreign_requests=foreign_requests,
        finished_requests=finished_requests,
        latest_news=latest_news,
    )


@app.route("/take_request/<int:id>", methods=["POST"])
@login_required
def take_request(id):
    req = HelpRequest.query.get_or_404(id)
    # доброволецът поема заявката
    req.email = current_user.email
    req.status = "Активен"
    db.session.commit()
    flash("Заявката е поета!", "success")
    return redirect(url_for("volunteer_dashboard"))


@app.route("/edit_request/<int:id>", methods=["GET", "POST"])
def edit_request(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    req = HelpRequest.query.get_or_404(id)
    if request.method == "POST":
        req.title = request.form.get("title", req.title)
        req.description = request.form.get("description", req.description)
        req.status = request.form.get("status", req.status)
        db.session.commit()
        flash("Заявката е редактирана!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("edit_request.html", req=req)


@app.route("/delete_request/<int:id>", methods=["POST"])
def delete_request(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    req = HelpRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash("Заявката е изтрита!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/approve_request/<int:id>", methods=["POST"])
def approve_request(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    req = HelpRequest.query.get_or_404(id)

    # Запазваме стария статус за лога
    old_status = req.status
    req.status = "Активен"
    db.session.commit()

    # Записваме в лога
    log_admin_action(
        action="approved_request",
        details={
            "request_id": req.id,
            "request_title": req.title,
            "old_status": old_status,
            "new_status": "Активен",
            "requester_name": req.name,
            "requester_email": req.email,
        },
        entity_type="help_request",
        entity_id=req.id,
    )

    flash("Заявката е одобрена!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/reject_request/<int:id>", methods=["POST"])
def reject_request(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    req = HelpRequest.query.get_or_404(id)

    # Запазваме стария статус за лога
    old_status = req.status
    req.status = "Отхвърлена"
    db.session.commit()

    # Записваме в лога
    log_admin_action(
        action="rejected_request",
        details={
            "request_id": req.id,
            "request_title": req.title,
            "old_status": old_status,
            "new_status": "Отхвърлена",
            "requester_name": req.name,
            "requester_email": req.email,
        },
        entity_type="help_request",
        entity_id=req.id,
    )

    flash("Заявката е отхвърлена!", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/export_requests")
def export_requests():
    if not admin_required():
        return redirect(url_for("admin_login"))
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Име", "Имейл", "Телефон", "Статус", "Описание", "Дата"])
    for req in HelpRequest.query.order_by(HelpRequest.id.asc()).all():
        writer.writerow(
            [
                req.id,
                req.name,
                req.email,
                req.phone,
                req.status,
                req.description,
                req.timestamp.strftime("%d.%m.%Y %H:%M") if req.timestamp else "",
            ]
        )
    output = "\ufeff" + si.getvalue()
    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=requests.csv"},
    )


@app.route("/add_news", methods=["POST"])
def add_news():
    if not admin_required():
        return redirect(url_for("admin_login"))
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if title and content:
        news = SuccessStory(title=title, content=content)
        db.session.add(news)
        db.session.commit()

        # Записваме в лога
        log_admin_action(
            action="added_news",
            details={
                "news_title": title,
                "news_content": (
                    content[:100] + "..." if len(content) > 100 else content
                ),
            },
            entity_type="success_story",
            entity_id=news.id,
        )

        flash("Новината е добавена!", "success")
    else:
        flash("Попълни всички полета!", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin_logs")
def admin_logs():
    """Показва историята на административни действия"""
    if not admin_required():
        return redirect(url_for("admin_login"))

    # Проверява дали потребителят може да вижда логове
    admin_user = get_current_admin_user()
    if admin_user and not admin_user.can_view_logs():
        flash("Нямате достъп до логовете.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Параметри за филтриране
    action_filter = request.args.get("action", "")
    entity_type_filter = request.args.get("entity_type", "")
    admin_filter = request.args.get("admin", "")
    page = request.args.get("page", 1, type=int)
    per_page = 50  # Показва 50 логове на страница

    # Строим заявката
    query = AdminLog.query

    if action_filter:
        query = query.filter(AdminLog.action.contains(action_filter))

    if entity_type_filter:
        query = query.filter(AdminLog.entity_type == entity_type_filter)

    if admin_filter:
        admin_users = AdminUser.query.filter(
            AdminUser.username.contains(admin_filter)
        ).all()
        admin_ids = [au.id for au in admin_users]
        if admin_ids:
            query = query.filter(AdminLog.admin_user_id.in_(admin_ids))

    # Подреждаме по дата (най-новите първо) и пагинираме
    logs = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Вземаме уникални стойности за филтрите
    unique_actions = db.session.query(AdminLog.action).distinct().all()
    unique_entity_types = (
        db.session.query(AdminLog.entity_type)
        .filter(AdminLog.entity_type.isnot(None))
        .distinct()
        .all()
    )
    unique_admins = db.session.query(AdminUser.username).distinct().all()

    return render_template(
        "admin_logs.html",
        logs=logs,
        unique_actions=[a[0] for a in unique_actions],
        unique_entity_types=[et[0] for et in unique_entity_types],
        unique_admins=[ua[0] for ua in unique_admins],
        action_filter=action_filter,
        entity_type_filter=entity_type_filter,
        admin_filter=admin_filter,
    )


@app.route("/admin_2fa_setup", methods=["GET", "POST"])
def admin_2fa_setup():
    """Настройка на двустепенна автентикация"""
    if not admin_required():
        return redirect(url_for("admin_login"))

    admin_user = get_current_admin_user()
    if not admin_user:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "enable":
            # Стъпка 1: Генериране на secret ключ
            if not admin_user.totp_secret:
                admin_user.totp_secret = generate_totp_secret()
                db.session.commit()

            # Генериране на QR код
            qr_code = generate_qr_code(admin_user)
            backup_codes = generate_backup_codes()

            return render_template(
                "admin_2fa_setup.html",
                admin_user=admin_user,
                qr_code=qr_code,
                backup_codes=backup_codes,
                step="verify",
            )

        elif action == "verify":
            # Стъпка 2: Потвърждение на TOTP код
            totp_token = request.form.get("totp_token", "").strip()

            if verify_totp_token(admin_user, totp_token):
                # Активиране на 2FA
                admin_user.two_factor_enabled = True

                # Запазване на backup кодовете
                backup_codes = generate_backup_codes()
                admin_user.backup_codes = json.dumps(backup_codes)

                db.session.commit()

                # Записваме в лога
                log_admin_action("enabled_2fa", {"admin_username": admin_user.username})

                flash("Двустепенната автентикация е активирана успешно!", "success")
                return render_template(
                    "admin_2fa_setup.html",
                    admin_user=admin_user,
                    backup_codes=backup_codes,
                    step="completed",
                )
            else:
                flash("Невалиден код! Моля опитайте отново.", "danger")
                qr_code = generate_qr_code(admin_user)
                backup_codes = generate_backup_codes()
                return render_template(
                    "admin_2fa_setup.html",
                    admin_user=admin_user,
                    qr_code=qr_code,
                    backup_codes=backup_codes,
                    step="verify",
                )

        elif action == "disable":
            # Деактивиране на 2FA
            totp_token = request.form.get("totp_token", "").strip()

            if verify_totp_token(admin_user, totp_token):
                admin_user.two_factor_enabled = False
                admin_user.totp_secret = None
                admin_user.backup_codes = None
                db.session.commit()

                # Записваме в лога
                log_admin_action(
                    "disabled_2fa", {"admin_username": admin_user.username}
                )

                flash("Двустепенната автентикация е деактивирана.", "info")
                return redirect(url_for("admin_2fa_setup"))
            else:
                flash("Невалиден код! Не можем да деактивираме 2FA.", "danger")

    return render_template(
        "admin_2fa_setup.html", admin_user=admin_user, step="initial"
    )


@app.route("/admin_2fa_backup_codes")
def admin_2fa_backup_codes():
    """Показва backup кодовете за 2FA"""
    if not admin_required():
        return redirect(url_for("admin_login"))

    admin_user = get_current_admin_user()
    if not admin_user or not admin_user.two_factor_enabled:
        flash("Двустепенната автентикация не е активирана.", "warning")
        return redirect(url_for("admin_2fa_setup"))

    try:
        backup_codes = json.loads(admin_user.backup_codes)
    except Exception:
        backup_codes = []

    return render_template(
        "admin_2fa_backup_codes.html", admin_user=admin_user, backup_codes=backup_codes
    )


@app.route("/admin_2fa_regenerate_backup", methods=["POST"])
def admin_2fa_regenerate_backup():
    """Регенерира backup кодовете"""
    if not admin_required():
        return redirect(url_for("admin_login"))

    admin_user = get_current_admin_user()
    if not admin_user or not admin_user.two_factor_enabled:
        flash("Двустепенната автентикация не е активирана.", "warning")
        return redirect(url_for("admin_2fa_setup"))

    # Потвърждение с TOTP код
    totp_token = request.form.get("totp_token", "").strip()

    if verify_totp_token(admin_user, totp_token):
        # Генериране на нови backup кодове
        backup_codes = generate_backup_codes()
        admin_user.backup_codes = json.dumps(backup_codes)
        db.session.commit()

        # Записваме в лога
        log_admin_action(
            "regenerated_backup_codes", {"admin_username": admin_user.username}
        )

        flash("Новите backup кодове са генерирани успешно!", "success")
        return render_template(
            "admin_2fa_backup_codes.html",
            admin_user=admin_user,
            backup_codes=backup_codes,
            new_codes=True,
        )
    else:
        flash("Невалиден код! Не можем да регенерираме backup кодовете.", "danger")
        return redirect(url_for("admin_2fa_backup_codes"))


@app.route("/delete_news/<int:id>", methods=["POST"])
def delete_news(id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    news = SuccessStory.query.get_or_404(id)
    db.session.delete(news)
    db.session.commit()
    flash("Новината е изтрита!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        # TODO: запис на промените в БД
        flash("Профилът е обновен успешно!")
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        # TODO: валидация и смяна на парола
        flash("Паролата е сменена успешно!")
        return redirect(url_for("profile"))
    return render_template("change_password.html")


@app.route("/upload_photo", methods=["GET", "POST"])
def upload_photo():
    if request.method == "POST":
        if "photo" not in request.files:
            flash("Няма избрана снимка!")
            return redirect(request.url)
        file = request.files["photo"]
        if file.filename == "":
            flash("Няма избрана снимка!")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filepath = UPLOAD_DIR / file.filename
            file.save(filepath)
            flash("Снимката е качена успешно!")
            # TODO: запиши пътя в БД
            return redirect(url_for("profile"))
        flash("Неподдържан формат!", "warning")
        return redirect(request.url)
    return render_template("upload_photo.html")


# -----------------------------------------------------------------------------
# Analytics Dashboard Routes
# -----------------------------------------------------------------------------


@app.route("/admin/analytics")
def admin_analytics():
    """Advanced Analytics Dashboard"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    try:
        # Импортираме analytics функционалностите
        from admin_analytics import AnalyticsEngine, RealtimeUpdates, RequestFilter

        # Получаваме параметри от URL
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        status = request.args.get("status", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        location = request.args.get("location", "")
        keyword = request.args.get("keyword", "")
        category = request.args.get("category", "")

        # Конвертираме датите
        date_from_obj = None
        date_to_obj = None
        try:
            if date_from:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            if date_to:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            flash("Невалиден формат на дата", "error")

        # Получаваме статистики
        stats = AnalyticsEngine.get_dashboard_stats(days=30)

    except Exception as e:
        print(f"❌ Analytics Error: {e}")
        import traceback

        traceback.print_exc()
        flash(f"Грешка в analytics: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        # Филтрираме заявки
        filtered_requests = RequestFilter.filter_requests(
            status=status or None,
            date_from=date_from_obj,
            date_to=date_to_obj,
            location=location or None,
            keyword=keyword or None,
            category=category or None,
            page=page,
            per_page=per_page,
        )

        # Получаваме опции за филтри
        filter_options = RequestFilter.get_filter_options()

        # Геолокационни данни
        geo_data = AnalyticsEngine.get_geo_data()

        # Последна активност
        recent_activity = RealtimeUpdates.get_recent_activity(limit=10)

        # Допълнителни статистики
        success_rate = AnalyticsEngine.get_success_rate()
        today_requests = HelpRequest.query.filter(
            db.func.date(HelpRequest.created_at) == datetime.utcnow().date()
        ).count()
        new_today = today_requests  # За простота

        # Най-активен доброволец (симулация)
        top_volunteer = Volunteer.query.first()

        # Най-честа категория
        try:
            if stats["category_stats"] and len(stats["category_stats"]) > 0:
                top_category = max(stats["category_stats"].items(), key=lambda x: x[1])[
                    0
                ]
            else:
                top_category = "Няма данни"
        except (TypeError, ValueError, KeyError):
            top_category = "Няма данни"

        # Проверяваме дали е AJAX заявка
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Връщаме JSON за AJAX обновяване
            return jsonify(
                {
                    "stats": stats,
                    "success_rate": success_rate,
                    "today_requests": today_requests,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    except Exception as e:
        print(f"❌ Data Processing Error: {e}")
        import traceback

        traceback.print_exc()
        flash(f"Грешка при обработка на данни: {str(e)}", "error")
        # Използваме fallback данни
        filtered_requests = {"items": [], "total": 0, "pages": 0, "current_page": 1}
        filter_options = {}
        geo_data = {"requests": [], "volunteers": []}
        recent_activity = []
        success_rate = 0
        new_today = 0
        top_volunteer = None
        top_category = "Няма данни"

    return render_template(
        "admin_analytics_dashboard.html",
        stats=stats,
        filtered_requests=filtered_requests,
        filter_options=filter_options,
        geo_data=geo_data,
        recent_activity=recent_activity,
        success_rate=success_rate,
        today_requests=today_requests,
        new_today=new_today,
        top_volunteer=top_volunteer,
        top_category=top_category,
        last_update=datetime.utcnow().strftime("%H:%M:%S"),
    )


# Добавяме маршрут /analytics, който пренасочва към /admin/analytics
@app.route("/analytics")
def analytics_redirect():
    return redirect(url_for("admin_analytics"))


@app.route("/admin/export")
def admin_export():
    """Export data in various formats"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    import csv
    from io import StringIO

    from admin_analytics import RequestFilter

    # Получаваме параметри
    export_format = request.args.get("export", "csv")
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    keyword = request.args.get("keyword", "")

    # Конвертираме датите
    date_from_obj = None
    date_to_obj = None
    try:
        if date_from:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        if date_to:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        pass

    # Получаваме всички данни (без пагинация)
    filtered_data = RequestFilter.filter_requests(
        status=status or None,
        date_from=date_from_obj,
        date_to=date_to_obj,
        keyword=keyword or None,
        page=1,
        per_page=10000,  # Голям брой за експорт
    )

    if export_format == "csv":
        # CSV експорт
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "ID",
                "Име",
                "Имейл",
                "Телефон",
                "Заглавие",
                "Описание",
                "Статус",
                "Дата на създаване",
            ]
        )

        # Data
        for req in filtered_data["items"]:
            writer.writerow(
                [
                    req.id,
                    req.name,
                    req.email,
                    req.phone or "",
                    req.title or "",
                    req.description or req.message or "",
                    req.status,
                    req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else "",
                ]
            )

        output.seek(0)

        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = (
            f'attachment; filename=helpchain_requests_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        )

        return response

    elif export_format == "json":
        # JSON експорт
        data = {
            "export_date": datetime.utcnow().isoformat(),
            "total_records": len(filtered_data["items"]),
            "filters": {
                "status": status,
                "date_from": date_from,
                "date_to": date_to,
                "keyword": keyword,
            },
            "requests": [],
        }

        for req in filtered_data["items"]:
            data["requests"].append(
                {
                    "id": req.id,
                    "name": req.name,
                    "email": req.email,
                    "phone": req.phone,
                    "title": req.title,
                    "description": req.description or req.message,
                    "status": req.status,
                    "created_at": (
                        req.created_at.isoformat() if req.created_at else None
                    ),
                }
            )

        response = make_response(json.dumps(data, ensure_ascii=False, indent=2))
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        response.headers["Content-Disposition"] = (
            f'attachment; filename=helpchain_requests_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
        )

        return response

    else:
        flash("Неподдържан формат за експорт", "error")
        return redirect(url_for("admin_analytics"))


@app.route("/admin/request/<int:request_id>/status", methods=["POST"])
def update_request_status():
    """Update request status via AJAX"""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Неоторизиран достъп"})

    try:
        request_id = request.json.get("id")
        new_status = request.json.get("status")

        help_request = HelpRequest.query.get_or_404(request_id)
        help_request.status = new_status

        db.session.commit()

        # Логване на действието
        try:
            from .models import AdminLog

            log = AdminLog(
                admin_user_id=session.get("admin_user_id", 1),  # Default admin
                action="status_change",
                details=f'Променен статус на заявка #{request_id} към "{new_status}"',
                entity_type="help_request",
                entity_id=request_id,
                ip_address=request.remote_addr,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            pass  # Не спираме заради логване

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/admin/live-stats")
def admin_live_stats():
    """Get live statistics for dashboard updates"""
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    from admin_analytics import RealtimeUpdates

    try:
        live_stats = RealtimeUpdates.get_live_stats()
        return jsonify(live_stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/geo-data")
def admin_geo_data():
    """Get geographical data for map"""
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    from admin_analytics import AnalyticsEngine

    try:
        geo_data = AnalyticsEngine.get_geo_data()
        return jsonify(geo_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Стартиране
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Първоначално създай БД таблиците, ако липсват (за локална разработка)
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            app.logger.warning("DB create_all skipped or failed: %s", exc)

    app.run(host="0.0.0.0", port=5000, debug=True)
