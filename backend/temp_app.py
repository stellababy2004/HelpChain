import csv
import os
from io import StringIO
from unittest.mock import patch

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
from flask_babel import Babel
from flask_babel import gettext as _
from flask_mail import Mail
from flask_migrate import Migrate
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.exc import OperationalError
from werkzeug.utils import secure_filename

# Поправи всички relative imports на absolute
try:
    from models import Volunteer, db
except Exception:
    # Fallback for package import path
    from backend.models import Volunteer, db  # Вместо 'from .models import'

# Import for 2FA testing
# try:
#     from models_with_analytics import AdminUser, AdminRole
#     from werkzeug.security import generate_password_hash, check_password_hash
#     import pyotp
#     HAS_2FA = True
#     print("2FA modules loaded successfully")
# except ImportError as e:
#     HAS_2FA = False
#     print(f"2FA modules not available: {e}")

#     # Fallback 2FA simulation using session
#     class MockAdminUser:
#         def __init__(self):
#             self.two_factor_enabled = False
#             self.totp_secret = None

#         def generate_totp_secret(self):
#             if not self.totp_secret:
#                 self.totp_secret = pyotp.random_base32()
#             return self.totp_secret

#         def get_totp_uri(self):
#             if not self.totp_secret:
#             self.generate_totp_secret()
#             return f"otpauth://totp/HelpChain:admin?secret={self.totp_secret}&issuer=HelpChain"

#         def verify_totp(self, token):
#             if not self.totp_secret:
#                 return False
#             totp = pyotp.TOTP(self.totp_secret)
#             return totp.verify(token)

#         def enable_2fa(self):
#             self.two_factor_enabled = True

#         def disable_2fa(self):
#             self.two_factor_enabled = False
#             self.totp_secret = None

#     mock_admin = MockAdminUser()
#     AdminUser = MockAdminUser  # Replace with mock

HAS_2FA = False
mock_admin = None

# Зареди environment variables от .env файла (от корена на проекта)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Създай папката instance ако не съществува
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

# Задаваме явни папки за шаблони и статични файлове (адаптирай пътищата ако е нужно)
_templates = os.path.join(
    os.path.dirname(__file__), "helpchain-backend", "src", "templates"
)
_static = os.path.join(os.path.dirname(__file__), "helpchain-backend", "src", "static")

# Създаваме приложението с правилните пътища
app = Flask(__name__, template_folder=_templates, static_folder=_static)

# Абсолютен път до базата за по-голяма сигурност
basedir = os.path.abspath(os.path.dirname(__file__))
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f"sqlite:///{os.path.join(basedir, 'instance', 'volunteers.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

# Езици
app.config["BABEL_DEFAULT_LOCALE"] = "bg"
app.config["BABEL_SUPPORTED_LOCALES"] = ["bg", "en"]
babel = Babel(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key_for_development")

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

mail = Mail(app)

# Настройваме Jinja да търси шаблони в няколко възможни директории
_template_dirs = [
    os.path.join(os.path.dirname(__file__), "templates"),
    os.path.join(os.path.dirname(__file__), "HelpChain.bg", "backend", "templates"),
    os.path.join(os.path.dirname(__file__), "helpchain-backend", "src", "templates"),
]
_loaders = [FileSystemLoader(d) for d in _template_dirs if os.path.isdir(d)]
# добавяме текущия loader в края (ако има)
if _loaders:
    app.jinja_loader = ChoiceLoader(
        _loaders + ([app.jinja_loader] if getattr(app, "jinja_loader", None) else [])
    )


@app.route("/")
def index():
    # безопасно извличаме агрегати — ако моделът липсва или схемата
    # не е съвместима, връщаме fallback
    try:
        volunteers_count = Volunteer.query.count() if "Volunteer" in globals() else 0
    except OperationalError:
        volunteers_count = 0
    except Exception:
        volunteers_count = 0

    try:
        HelpRequestModel = globals().get("HelpRequest")
        if HelpRequestModel is not None:
            requests_count = HelpRequestModel.query.count()
            open_requests = HelpRequestModel.query.filter(
                HelpRequestModel.status != "completed"
            ).count()
        else:
            requests_count = 0
            open_requests = 0
    except OperationalError:
        requests_count = 0
        open_requests = 0
    except Exception:
        requests_count = 0
        open_requests = 0

    if app.jinja_loader:
        return render_template(
            "index.html",
            volunteers_count=volunteers_count,
            requests_count=requests_count,
            open_requests=open_requests,
        )
    return (
        jsonify(
            {
                "volunteers_count": volunteers_count,
                "requests_count": requests_count,
                "open_requests": open_requests,
            }
        ),
        200,
    )


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Simple check for demo
        if username == "admin" and password == "admin123":
            if HAS_2FA and mock_admin.two_factor_enabled:
                session["pending_2fa"] = True
                return redirect(url_for("admin_2fa"))
            else:
                session["admin_logged_in"] = True
                return redirect(url_for("admin_dashboard"))
        else:
            error = "Грешно потребителско име или парола!"
    return render_template("admin_login.html", error=error)


@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    requests = {
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
        "admin_dashboard.html", requests=requests, logs_dict=logs_dict
    )


@app.route("/admin/2fa", methods=["GET", "POST"])
def admin_2fa():
    if not session.get("pending_2fa"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        token = request.form.get("token")
        if mock_admin.verify_totp(token):
            session["admin_logged_in"] = True
            session.pop("pending_2fa", None)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Невалиден 2FA код.", "error")

    return render_template("admin_2fa.html")


@app.route("/admin/2fa/setup", methods=["GET", "POST"])
def admin_2fa_setup():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        token = request.form.get("token")
        if mock_admin.verify_totp(token):
            mock_admin.enable_2fa()
            flash("2FA е активиран успешно!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Невалиден код.", "error")

    uri = mock_admin.get_totp_uri()
    return render_template("admin_2fa_setup.html", totp_uri=uri)


@app.route("/admin/2fa/disable", methods=["POST"])
def admin_2fa_disable():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    mock_admin.disable_2fa()
    flash("2FA е деактивиран.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin_volunteers", methods=["GET", "POST"])
def admin_volunteers():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteers = Volunteer.query.all()
    return render_template("admin_volunteers.html", volunteers=volunteers)


@app.route("/admin_volunteers/add", methods=["GET", "POST"])
def add_volunteer():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        location = request.form["location"]  # <-- нов ред
        volunteer = Volunteer(name=name, email=email, phone=phone, location=location)
        db.session.add(volunteer)
        db.session.commit()
        flash("Доброволецът е добавен успешно!", "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("add_volunteer.html")


@app.route("/submit_request", methods=["GET", "POST"])
def submit_request():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        category = request.form.get("category")
        location = request.form.get("location")
        problem = request.form.get("problem")
        terms = request.form.get("terms")
        captcha = request.form.get("captcha")
        file = request.files.get("file")

        if captcha != "7G5K":
            flash("Грешен код за защита!")
            return redirect(url_for("submit_request"))

        filename = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Позволени са само изображения и PDF!")
                return redirect(url_for("submit_request"))
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

        # Използваме подадените полета (логваме) за да не са "unused"
        request_data = {
            "name": name,
            "email": email,
            "category": category,
            "location": location,
            "problem": problem,
            "terms": terms,
            "filename": filename,
        }
        app.logger.info("submit_request received: %s", request_data)

        return render_template("submit_success.html")
    return render_template("submit_request.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        location = request.form.get("location")
        volunteer = Volunteer(name=name, email=email, phone=phone, location=location)
        db.session.add(volunteer)
        db.session.commit()
        flash("Успешна регистрация! Ще се свържем с вас при нужда.")
        return redirect(url_for("volunteer_register"))
    return render_template("volunteer_register.html")


@app.route("/become_volunteer")
def become_volunteer():
    """Пренасочване към страницата за регистрация на доброволци"""
    return redirect(url_for("volunteer_register"))


@app.route("/delete_volunteer/<int:id>", methods=["POST"])
def delete_volunteer(id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    db.session.delete(volunteer)
    db.session.commit()
    flash("Доброволецът е изтрит успешно!", "success")
    return redirect(url_for("admin_volunteers"))


@app.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
def edit_volunteer(id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    if request.method == "POST":
        volunteer.name = request.form["name"]
        volunteer.email = request.form["email"]
        volunteer.phone = request.form["phone"]
        volunteer.location = request.form["location"]  # Добави и локацията тук
        db.session.commit()
        flash("Промените са запазени!", "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("edit_volunteer.html", volunteer=volunteer)


@app.route("/export_volunteers")
def export_volunteers():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteers = Volunteer.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Име", "Имейл", "Телефон", "Град/регион"])
    for v in volunteers:
        cw.writerow([v.name, v.email, v.phone, v.location])
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=volunteers.csv"},
    )


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/success_stories")
def success_stories():
    return render_template("success_stories.html")


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        # Логваме обратната връзка (използваме променливите)
        app.logger.info("Feedback received from %s <%s>: %s", name, email, message)
        flash("Благодарим за обратната връзка!")
        return redirect(url_for("feedback"))
    return render_template("feedback.html")


@app.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form["language"]
    resp = make_response(redirect(request.referrer or url_for("index")))
    resp.set_cookie("language", lang)
    return resp


@app.route("/admin")
def admin():
    return redirect(url_for("admin_login"))


@app.route("/update_status/<int:req_id>", methods=["POST"])
def update_status(req_id):
    return jsonify({"success": True})


@app.route("/admin_volunteers/<int:id>")
def volunteer_detail(id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    volunteer = Volunteer.query.get_or_404(id)
    return render_template("volunteer_detail.html", volunteer=volunteer)


@app.route("/admin_volunteers/search")
def search_volunteers():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    q = request.args.get("q", "")
    volunteers = Volunteer.query.filter(
        (Volunteer.name.ilike(f"%{q}%")) | (Volunteer.email.ilike(f"%{q}%"))
    ).all()
    return render_template("admin_volunteers.html", volunteers=volunteers, q=q)


@app.context_processor
def inject_gettext():
    return dict(_=_)


@app.context_processor
def inject_get_locale():
    def get_locale():
        return request.cookies.get("language") or request.accept_languages.best_match(
            ["bg", "en"]
        )

    return dict(get_locale=get_locale)


# Debug принтове за mail настройките (добави MAILTRAP)
# print("MAILTRAP_USERNAME:", os.getenv("MAILTRAP_USERNAME"))
# print("MAILTRAP_PASSWORD:", os.getenv("MAILTRAP_PASSWORD"))
# print("MAIL_SERVER:", os.getenv("MAIL_SERVER"))
# print("MAIL_PORT:", os.getenv("MAIL_PORT"))
# print("MAIL_USE_SSL:", os.getenv("MAIL_USE_SSL"))
# print("MAIL_USE_TLS:", os.getenv("MAIL_USE_TLS"))
# print("MAIL_USERNAME:", os.getenv("MAIL_USERNAME"))
# print("MAIL_PASSWORD:", os.getenv("MAIL_PASSWORD"))

if os.getenv("MAIL_PORT"):
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT"))
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL") == "True"
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS") == "True"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
else:
    print(
        "Warning: MAIL_PORT environment variable is not set! Имейл функционалността няма да работи."
    )

# В секцията за mail config, подобри логиката за MAILTRAP/Zoho
mailtrap_username = os.getenv("MAILTRAP_USERNAME")
if mailtrap_username:
    app.config["MAIL_SERVER"] = "sandbox.smtp.mailtrap.io"
    app.config["MAIL_PORT"] = 2525
    app.config["MAIL_USE_SSL"] = False
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = mailtrap_username
    app.config["MAIL_PASSWORD"] = os.getenv("MAILTRAP_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = "contact@helpchain.live"
    print("Using MAILTRAP for emails")
else:
    # Zoho настройки по подразбиране
    app.config["MAIL_SERVER"] = "smtp.zoho.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_SSL"] = False
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = "contact@helpchain.live"
    print("Using Zoho for emails")


@app.route("/admin", methods=["GET"])
def admin_panel():
    from flask import current_app  # Локален import за избягване на circular import

    # Опитай да рендерираш template 'admin.html' ако съществува, иначе върни прост HTML
    try:
        # проверка дали шаблонът е наличен
        if current_app.jinja_loader and current_app.jinja_loader.list_templates():
            return render_template("admin.html")
    except Exception:
        # падане към fallback
        pass

    # fallback прост HTML (явно ще се вижда в браузъра)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Admin</title>"
        "<style>body{font-family:Arial,Helvetica,sans-serif;padding:1rem}"
        "h1{font-size:18px}</style></head><body><h1>Admin panel (placeholder)</h1>"
        "<p>Шаблонът admin.html не е намерен.</p></body></html>",
        200,
    )


# Добави mock за mail.send за тестване (симулира изпращане без реални SMTP заявки)

# Mock mail.send за всички изпращания на имейли
mock_mail_send = patch.object(
    mail,
    "send",
    side_effect=lambda msg: app.logger.info(
        f"Mocked email sent: {msg.subject} to {msg.recipients}"
    ),
).start()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)

# За да спреш mock-а в production, добави:
# mock_mail_send.stop()  # Премахни за реални имейли
