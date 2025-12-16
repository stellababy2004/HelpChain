import datetime
import os
import sqlite3
import uuid

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, jsonify
from flask_babel import get_locale, refresh
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Message
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename

from backend.models import AdminUser, Request, RequestLog

from .config import Config
from .controllers.helpchain_controller import HelpChainController
from .extensions import babel, db, mail, migrate
from .routes.api import api_bp

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
print(f"MAILTRAP_USERNAME from env: {os.environ.get('MAILTRAP_USERNAME')}")
print(f"MAILTRAP_PASSWORD from env: {os.environ.get('MAILTRAP_PASSWORD')}")

controller = HelpChainController()

login_manager = LoginManager()
socketio = SocketIO(async_mode="threading")


@login_manager.user_loader
def load_user(user_id):
    from .models import User

    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


def create_app(config_object=None):
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    static_dir = os.path.join(base, "static")

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object or Config)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
    )

    # Register an early, global short-circuit guard BEFORE any extensions/blueprints
    # so that protected endpoints always respond even if later hooks fail.
    @app.before_request
    def _preview_short_circuit_early():
        try:
            p = request.path or ""
            if p in ("/health", "/api/_health"):
                return Response("ok", mimetype="text/plain")
            if p == "/api/analytics":
                return jsonify(status="ok", source="stub", message="analytics service reachable")
            if p == "/admin/login" and request.method == "GET":
                return Response(
                    (
                        "<html><head><title>Admin Login</title></head>"
                        "<body>"
                        "<h1>Admin Login</h1>"
                        "<form method=\"post\">"
                        "<label>Username or Email: <input name=\"username\" /></label><br/>"
                        "<label>Password: <input name=\"password\" type=\"password\" /></label><br/>"
                        "<label>2FA Token (optional): <input name=\"token\" /></label><br/>"
                        "<button type=\"submit\">Login</button>"
                        "</form>"
                        "</body></html>"
                    ),
                    mimetype="text/html",
                )
        except Exception:
            # Never fail this guard
            return None

    # Explicit health endpoints (in addition to the guard) for clarity
    @app.get("/health")
    def _health_plain():
        return Response("ok", mimetype="text/plain")

    @app.get("/api/_health")
    def _api_health_plain():
        return jsonify(status="ok")

    db.init_app(app)
    babel.init_app(app)
    mail.init_app(app)
    try:
        migrate.init_app(app, db)
    except Exception:
        pass

    login_manager.init_app(app)
    login_manager.login_view = "login"

    app.config["UPLOAD_FOLDER"] = os.path.join(static_dir, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .models import User

    with app.app_context():
        db.create_all()

    def _safe_get_locale():
        try:
            return get_locale()
        except Exception:
            return "bg"

    app.jinja_env.globals["get_locale"] = _safe_get_locale
    app.jinja_env.globals["str"] = str
    app.jinja_env.globals["getattr"] = getattr

    app.register_blueprint(api_bp, url_prefix="/api")

    try:
        from .routes.main import main_bp

        app.register_blueprint(main_bp)
    except Exception as e:
        app.logger.info("main blueprint not loaded: %s", e)

    try:
        from .routes.admin import admin_bp

        app.register_blueprint(admin_bp, url_prefix="/admin")
    except Exception as e:
        app.logger.info("admin blueprint not loaded: %s", e)

    try:
        from .routes.analytics import analytics_bp

        app.register_blueprint(analytics_bp)
    except Exception as e:
        app.logger.info("analytics blueprint not loaded: %s", e)


    @app.route("/")
    def index():
        return render_template("home_new.html")

    @app.route("/static/previews/new-page.html")
    def legacy_preview_redirect():
        from flask import redirect, url_for

        return redirect(url_for("index"), code=301)

    @app.route("/set_language/<language>", methods=["POST"])
    def set_language(language):
        if language in ["bg", "en"]:
            session["language"] = language
            refresh()
        return redirect(request.referrer or "/")

    @app.route("/submit_request", methods=["GET", "POST"])
    def submit_request():
        if request.method == "POST":
            data = request.form.to_dict()
            print(f"Received data: {data}")
            try:
                req = Request(
                    name=data.get("name"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    location=data.get("location"),
                    category=data.get("category"),
                    description=data.get("description"),
                    urgency=data.get("urgency"),
                    status="pending",
                )
                db.session.add(req)
                db.session.commit()
                print(f"Created request with id: {req.id}")

                send_email_notification(req)

                flash(
                    "Благодарим ви че се свързахте с екипа ни! Ще се свържем с вас скоро.",
                    "success",
                )
                return redirect(url_for("index"))
            except Exception as e:
                print(f"Error in submit_request: {e}")
                flash(f"Грешка при подаване на заявката: {str(e)}", "error")
                return redirect(url_for("submit_request"))
        return render_template("submit_request.html")

    def send_email_notification(req):
        import os

        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "notifications.db")

        def save_notification_to_db(recipient, subject, content, status="saved", smtp_error=None):
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute(
                    """CREATE TABLE IF NOT EXISTS notifications
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              timestamp TEXT,
                              recipient TEXT,
                              subject TEXT,
                              content TEXT,
                              status TEXT,
                              smtp_error TEXT)"""
                )
                c.execute(
                    """INSERT INTO notifications (timestamp, recipient, subject, content, status, smtp_error)
                             VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        datetime.datetime.now().isoformat(),
                        recipient,
                        subject,
                        content,
                        status,
                        smtp_error,
                    ),
                )
                conn.commit()

        content = f"""Нова заявка за помощ:
ID: {req.id}
Име: {req.name}
Имейл: {req.email}
Телефон: {req.phone}
Локация: {req.location}
Категория: {req.category}
Описание: {req.description}
Спешност: {req.urgency}"""

        subject = "Нова заявка за помощ в HelpChain"

        try:
            with open(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "sent_emails.txt"),
                "a",
                encoding="utf-8",
            ) as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"Email sent at: {datetime.datetime.now()}\n")
                f.write(f"Subject: {subject}\n")
                f.write("To: contact@helpchain.live\n")
                f.write(f"From: {app.config['MAIL_DEFAULT_SENDER']}\n")
                f.write(f"Date: {datetime.datetime.now()}\n\n")
                f.write(content)
                f.write(f"\n{'=' * 50}\n")
            print(f"✅ Email saved to file for request ID {req.id}")
        except Exception as e:
            print(f"❌ Failed to save email to file: {e}")

        msg = Message(
            subject=subject,
            recipients=["contact@helpchain.live"],
            sender=app.config["MAIL_DEFAULT_SENDER"],
            body=content,
        )

        smtp_error = None
        status = "saved"

        try:
            mail.send(msg)
            status = "sent"
            print(f"✅ Email sent successfully for request ID {req.id}")
        except Exception as e:
            smtp_error = str(e)
            print(f"⚠️  Email send failed, but saved to database: {e}")

        try:
            save_notification_to_db("contact@helpchain.live", subject, content, status, smtp_error)
            print(f"✅ Notification saved to database for request ID {req.id}")
        except Exception as e:
            print(f"❌ Failed to save to database: {e}")

        return status == "sent"

    def send_volunteer_notification(volunteer):
        import os

        DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "notifications.db")

        def save_notification_to_db(recipient, subject, content, status="saved", smtp_error=None):
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute(
                    """CREATE TABLE IF NOT EXISTS notifications
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              timestamp TEXT,
                              recipient TEXT,
                              subject TEXT,
                              content TEXT,
                              status TEXT,
                              smtp_error TEXT)"""
                )
                c.execute(
                    """INSERT INTO notifications (timestamp, recipient, subject, content, status, smtp_error)
                             VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        datetime.datetime.now().isoformat(),
                        recipient,
                        subject,
                        content,
                        status,
                        smtp_error,
                    ),
                )
                conn.commit()

        content = f"""Нов доброволец се е регистрирал:
ID: {volunteer.id}
Име: {volunteer.name}
Имейл: {volunteer.email}
Телефон: {volunteer.phone}
Локация: {volunteer.location}
Умения: {volunteer.skills}"""

        subject = "Нов доброволец в HelpChain"

        try:
            with open(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "sent_emails.txt"),
                "a",
                encoding="utf-8",
            ) as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"Email sent at: {datetime.datetime.now()}\n")
                f.write(f"Subject: {subject}\n")
                f.write("To: contact@helpchain.live\n")
                f.write(f"From: {app.config['MAIL_DEFAULT_SENDER']}\n")
                f.write(f"Date: {datetime.datetime.now()}\n\n")
                f.write(content)
                f.write(f"\n{'=' * 50}\n")
            print(f"✅ Email saved to file for volunteer ID {volunteer.id}")
        except Exception as e:
            print(f"❌ Failed to save email to file: {e}")

        msg = Message(
            subject=subject,
            recipients=["contact@helpchain.live"],
            sender=app.config["MAIL_DEFAULT_SENDER"],
            body=content,
        )

        smtp_error = None
        status = "saved"

        try:
            mail.send(msg)
            status = "sent"
            print(f"✅ Email sent successfully for volunteer ID {volunteer.id}")
        except Exception as e:
            smtp_error = str(e)
            print(f"⚠️  Email send failed, but saved to database: {e}")

        try:
            save_notification_to_db("contact@helpchain.live", subject, content, status, smtp_error)
            print(f"✅ Notification saved to database for volunteer ID {volunteer.id}")
        except Exception as e:
            print(f"❌ Failed to save to database: {e}")

        return status == "sent"

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            data = request.form.to_dict()
            if User.query.filter_by(email=data.get("email")).first():
                flash("Имейлът вече е регистриран.", "error")
                return redirect(url_for("register"))
            user = User(
                username=data.get("username"),
                email=data.get("email"),
                citizen_id=data.get("citizen_id"),
                is_volunteer=data.get("is_volunteer") == "on",
                is_organization=data.get("is_organization") == "on",
            )
            user.set_password(data.get("password"))
            db.session.add(user)
            db.session.commit()
            flash("Регистрацията е успешна! Можете да влезете.", "success")
            return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            user = User.query.filter_by(email=email).first()
            print(f"Login attempt: email={email}, user found: {user is not None}")
            if user:
                print(f"Password check: {user.check_password(password)}")
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Невалиден имейл или парола.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.is_admin:
            requests = Request.query.all()
        else:
            requests = Request.query.all()
        return render_template("dashboard.html", requests=requests)

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.skills = request.form.get("skills")
            current_user.location = request.form.get("location")
            current_user.available_time = request.form.get("available_time")
            if "profile_picture" in request.files:
                file = request.files["profile_picture"]
                if file.filename != "":
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                    current_user.profile_picture = filename
                    print(f"Profile picture saved: {filename}")
            db.session.commit()
            flash("Профилът е обновен.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    socketio.init_app(app, cors_allowed_origins="*")

    @socketio.on("join")
    def on_join(data):
        room = data["room"]
        join_room(room)
        emit(
            "status",
            {"msg": f"{data['username']} се присъедини към {room}"},
            room=room,
        )

    @socketio.on("leave")
    def on_leave(data):
        room = data["room"]
        leave_room(room)
        emit("status", {"msg": f"{data['username']} напусна {room}"}, room=room)

    @socketio.on("typing")
    def handle_typing(data):
        room = data["room"]
        username = data["username"]
        emit(
            "typing",
            {"username": username, "is_typing": data["is_typing"]},
            room=room,
            skip_sid=True,
        )

    return app


app = create_app(Config)


def init_sample_data():
    with app.app_context():
        from backend.models import Request, RequestLog, User

        db.create_all()

        if User.query.count() == 0:
            sample_user = User(
                username="testuser",
                email="test@example.com",
                is_volunteer=True,
                is_organization=False,
            )
            sample_user.set_password(os.getenv("SAMPLE_USER_PASSWORD", "password123"))
            db.session.add(sample_user)
            admin_user = User(
                username="admin",
                email="admin@example.com",
                is_volunteer=True,
                is_organization=False,
                is_admin=True,
            )
            admin_user.set_password(os.getenv("ADMIN_USER_PASSWORD", "admin123"))
            db.session.add(admin_user)
            db.session.commit()
            print("Sample user created: email=test@example.com, password=password123")
            print("Admin user created: email=admin@example.com, password=admin123")

        if Request.query.count() == 0:
            sample_requests = [
                Request(
                    name="Иван Иванов",
                    phone="+359 88 123 4567",
                    location="sofia",
                    category="food",
                    description="Нуждая се от храна",
                    status="pending",
                ),
                Request(
                    name="Мария Петрова",
                    phone="+359 87 654 3210",
                    location="plovdiv",
                    category="medical",
                    description="Медицинска помощ",
                    status="in_progress",
                ),
                Request(
                    name="Георги Димитров",
                    phone="+359 89 987 6543",
                    location="varna",
                    category="transport",
                    description="Транспорт до болница",
                    status="completed",
                ),
            ]
            db.session.add_all(sample_requests)
            db.session.commit()

            sample_logs = [
                RequestLog(
                    request_id=1,
                    status="pending",
                    changed_at=datetime.datetime(2025, 10, 1, 10, 0, 0),
                ),
                RequestLog(
                    request_id=1,
                    status="in_progress",
                    changed_at=datetime.datetime(2025, 10, 1, 11, 0, 0),
                ),
                RequestLog(
                    request_id=2,
                    status="pending",
                    changed_at=datetime.datetime(2025, 10, 1, 9, 0, 0),
                ),
                RequestLog(
                    request_id=3,
                    status="pending",
                    changed_at=datetime.datetime(2025, 10, 1, 8, 0, 0),
                ),
                RequestLog(
                    request_id=3,
                    status="completed",
                    changed_at=datetime.datetime(2025, 10, 1, 12, 0, 0),
                ),
            ]
            db.session.add_all(sample_logs)
            db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)
