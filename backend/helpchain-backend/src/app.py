import os
from dotenv import load_dotenv

# All imports at the top
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.utils import secure_filename

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from .config import Config
    from .extensions import db, babel, mail
    from .models import (
        Request,
        RequestLog,
        User,
        AdminUser,
        ChatRoom,
        ChatMessage,
    )
    from ...analytics_service import analytics_service
except ImportError:
    # Fallback for standalone execution
    import sys

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    sys.path.insert(0, backend_dir)

    from config import Config
    from extensions import db, babel, mail
    from models import (
        Request,
        RequestLog,
        User,
        AdminUser,
        ChatRoom,
        ChatMessage,
    )
    from analytics_service import analytics_service

from flask_babel import get_locale, refresh
from flask_mail import Message
import datetime
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
import sqlite3

# Try to import Migrate for database migrations
try:
    from flask_migrate import Migrate

    migrate_available = True
except ImportError:
    migrate_available = False

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
print(f"MAILTRAP_USERNAME from env: {os.environ.get('MAILTRAP_USERNAME')}")
print(f"MAILTRAP_PASSWORD from env: {os.environ.get('MAILTRAP_PASSWORD')}")

login_manager = LoginManager()
socketio = SocketIO()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app(config_object=None):
    # Задаваме абсолютни пътища към templates/static (относно този файл)
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    static_dir = os.path.join(base, "static")

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object or Config)

    # гарантираме, че предупреждението ще бъде заглушено по подразбиране
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # fallback за база при тестове (ако още не е зададена)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
    )

    # инициализация на разширения (db, babel, mail, migrate)
    db.init_app(app)
    babel.init_app(app)
    mail.init_app(app)
    # migrate може да бъде инициализиран с app и db
    if migrate_available:
        migrate = Migrate(app, db)
    else:
        migrate = None

    # Initialize login manager
    login_manager.init_app(app)
    login_manager.login_view = "login"

    # Create upload folder
    app.config["UPLOAD_FOLDER"] = os.path.join(static_dir, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Import models before creating tables
    # from .models import Request, RequestLog, Volunteer, Feedback, User  # Remove this duplicate import

    # Create tables
    with app.app_context():
        db.create_all()

        # Check if users table is empty
        if User.query.count() == 0:
            # Create a sample user
            sample_user = User(
                username="testuser",
                email="test@example.com",
                is_volunteer=True,
                is_organization=False,
            )
            sample_user.set_password(os.getenv("SAMPLE_USER_PASSWORD", "password123"))
            db.session.add(sample_user)
            # Create admin user
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

        # Check if AdminUser table is empty and create default admin
        if AdminUser.query.count() == 0:
            admin_user = AdminUser(
                username="admin",
                email="admin@helpchain.live",
            )
            admin_user.set_password(os.getenv("ADMIN_USER_PASSWORD", "admin123"))
            db.session.add(admin_user)
            db.session.commit()
            print("AdminUser created: username=admin, password=admin123")

        # Add sample data if empty
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

    # expose safe get_locale to Jinja templates so base.html can call get_locale()
    def _safe_get_locale():
        try:
            return get_locale()
        except Exception:
            return "bg"

    app.jinja_env.globals["get_locale"] = _safe_get_locale

    # expose builtins used by templates
    app.jinja_env.globals["str"] = str
    app.jinja_env.globals["getattr"] = getattr

    # Регистрираме API blueprint под /api
    # try:
    #     from routes.api import api_bp
    #     app.register_blueprint(api_bp, url_prefix="/api")
    # except Exception as e:
    #     app.logger.info("api blueprint not loaded: %s", e)

    # Регистрираме main blueprint (основни публични страници)
    # try:
    #     from routes.main import main_bp
    #     app.register_blueprint(main_bp)
    # except Exception as e:
    #     app.logger.info("main blueprint not loaded: %s", e)

    # Регистрираме admin blueprint под /admin
    # try:
    #     from routes.admin import admin_bp
    #     app.register_blueprint(admin_bp, url_prefix="/admin")
    # except Exception as e:
    #     app.logger.info("admin blueprint not loaded: %s", e)

    # Регистрираме analytics blueprint (pages + api + stream)
    # try:
    #     from routes.analytics import analytics_bp
    #     app.register_blueprint(analytics_bp)
    # except Exception as e:
    #     app.logger.info("analytics blueprint not loaded: %s", e)

    # Ако няма index шаблон/маршрут в appy, осигуряваме прост home route
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/set_language/<language>", methods=["POST"])
    def set_language(language):
        if language in ["bg", "en"]:
            session["language"] = language
            refresh()
        return redirect(request.referrer or "/")

    # Добавени липсващи маршрути за тестовете
    @app.route("/submit_request", methods=["GET", "POST"])
    def submit_request():
        if request.method == "POST":
            data = request.form.to_dict()
            print(f"Received data: {data}")  # Debug log
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
                print(f"Created request with id: {req.id}")  # Debug log

                # Send email notification
                send_email_notification(req)

                flash(
                    "Благодарим ви че се свързахте с екипа ни! Ще се свържем с вас скоро.",
                    "success",
                )
                return redirect(url_for("index"))
            except Exception as e:
                print(f"Error in submit_request: {e}")  # Debug log
                flash(f"Грешка при подаване на заявката: {str(e)}", "error")
                return redirect(url_for("submit_request"))
        return render_template("submit_request.html")

    def send_email_notification(req):
        import os

        # Database setup for notifications
        DB_PATH = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "notifications.db"
        )

        def save_notification_to_db(
            recipient, subject, content, status="saved", smtp_error=None
        ):
            """Save notification to database"""
            conn = sqlite3.connect(DB_PATH)
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
            conn.close()

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

        # Save to file (backup)
        try:
            with open(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "..", "sent_emails.txt"
                ),
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

        # Try to send real email
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

        # Save to database
        try:
            save_notification_to_db(
                "contact@helpchain.live", subject, content, status, smtp_error
            )
            print(f"✅ Notification saved to database for request ID {req.id}")
        except Exception as e:
            print(f"❌ Failed to save to database: {e}")

        return status == "sent"

    # Добави тази функция след send_email_notification
    def send_volunteer_notification(volunteer):
        import os

        # Database setup for notifications
        DB_PATH = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "notifications.db"
        )

        def save_notification_to_db(
            recipient, subject, content, status="saved", smtp_error=None
        ):
            """Save notification to database"""
            conn = sqlite3.connect(DB_PATH)
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
            conn.close()

        content = f"""Нов доброволец се е регистрирал:
ID: {volunteer.id}
Име: {volunteer.name}
Имейл: {volunteer.email}
Телефон: {volunteer.phone}
Локация: {volunteer.location}
Умения: {volunteer.skills}"""

        subject = "Нов доброволец в HelpChain"

        # Save to file (backup)
        try:
            with open(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "..", "sent_emails.txt"
                ),
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

        # Try to send real email
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

        # Save to database
        try:
            save_notification_to_db(
                "contact@helpchain.live", subject, content, status, smtp_error
            )
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
                citizen_id=data.get("citizen_id"),  # Добави
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
            print(
                f"Login attempt: email={email}, user found: {user is not None}"
            )  # Debug
            if user:
                print(f"Password check: {user.check_password(password)}")  # Debug
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

    @app.route("/volunteer_logout")
    @login_required
    def volunteer_logout():
        logout_user()
        flash("Успешен изход", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # Show user's requests or activities
        if current_user.is_admin:
            requests = Request.query.all()
        else:
            # For non-admin users, show all requests (or filter as needed)
            requests = Request.query.all()  # Changed to show all requests for non-admin
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
                    print(f"Profile picture saved: {filename}")  # Debug
            db.session.commit()
            flash("Профилът е обновен.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    # Video Chat Routes
    @app.route("/video_chat")
    @login_required
    def video_chat():
        """Показва списък с активни видео чат сесии"""
        from .models import VideoChatSession, User

        # Показваме активни сесии където текущият потребител участва
        active_sessions = VideoChatSession.query.filter(
            (
                (VideoChatSession.initiator_id == current_user.id)
                | (VideoChatSession.participant_id == current_user.id)
            )
            & (VideoChatSession.status.in_(["pending", "active"]))
        ).all()

        # Показваме онлайн потребители (опростена версия - всички регистрирани)
        online_users = User.query.filter(User.id != current_user.id).all()

        return render_template(
            "video_chat.html",
            active_sessions=active_sessions,
            online_users=online_users,
        )

    @app.route("/video_chat/start/<int:user_id>", methods=["POST"])
    @login_required
    def start_video_chat(user_id):
        """Започва нова видео чат сесия с даден потребител"""
        from .models import VideoChatSession, User

        participant = User.query.get_or_404(user_id)

        # Проверяваме дали вече има активна сесия между тези потребители
        existing_session = VideoChatSession.query.filter(
            (
                (VideoChatSession.initiator_id == current_user.id)
                & (VideoChatSession.participant_id == user_id)
            )
            | (
                (VideoChatSession.initiator_id == user_id)
                & (VideoChatSession.participant_id == current_user.id)
            ),
            VideoChatSession.status.in_(["pending", "active"]),
        ).first()

        if existing_session:
            flash("Вече има активна видео чат сесия с този потребител.", "warning")
            return redirect(url_for("video_chat"))

        # Създаваме нова сесия
        session_id = str(uuid.uuid4())
        video_session = VideoChatSession(
            session_id=session_id,
            initiator_id=current_user.id,
            participant_id=user_id,
            status="pending",
        )

        db.session.add(video_session)
        db.session.commit()

        # Track video chat event for analytics
        try:
            from ...analytics_service import analytics_service

            analytics_service.track_event(
                event_type="video_chat_started",
                event_category="communication",
                event_action="start_session",
                context={
                    "participant_id": user_id,
                    "session_id": session_id,
                    "user_agent": request.headers.get("User-Agent"),
                    "ip_address": request.remote_addr,
                },
            )
        except Exception as analytics_error:
            print(f"Analytics tracking failed: {analytics_error}")

        flash(f"Видео чат сесия е започната с {participant.username}.", "success")
        return redirect(url_for("join_video_chat", session_id=session_id))

    @app.route("/video_chat/join/<session_id>")
    @login_required
    def join_video_chat(session_id):
        """Присъединява се към видео чат сесия"""
        from .models import VideoChatSession

        session = VideoChatSession.query.filter_by(session_id=session_id).first_or_404()

        # Проверяваме дали текущият потребител има право да се присъедини
        if (
            session.initiator_id != current_user.id
            and session.participant_id != current_user.id
        ):
            flash("Нямате право да се присъедините към тази сесия.", "error")
            return redirect(url_for("video_chat"))

        # Ако сесията е pending и текущият потребител е participant, я активираме
        if session.status == "pending" and session.participant_id == current_user.id:
            session.status = "active"
            session.started_at = datetime.datetime.utcnow()
            db.session.commit()

        return render_template(
            "video_chat_room.html", session=session, current_user=current_user
        )

    @app.route("/video_chat/end/<session_id>", methods=["POST"])
    @login_required
    def end_video_chat(session_id):
        """Завършва видео чат сесия"""
        from .models import VideoChatSession

        session = VideoChatSession.query.filter_by(session_id=session_id).first_or_404()

        # Проверяваме дали текущият потребител участва в сесията
        if (
            session.initiator_id != current_user.id
            and session.participant_id != current_user.id
        ):
            flash("Нямате право да завършите тази сесия.", "error")
            return redirect(url_for("video_chat"))

        # Изчисляваме продължителността
        if session.started_at and not session.ended_at:
            session.ended_at = datetime.datetime.utcnow()
            duration = (session.ended_at - session.started_at).total_seconds()
            session.duration = int(duration)

        session.status = "completed"
        db.session.commit()

        # Track video chat end event for analytics
        try:
            from ...analytics_service import analytics_service

            analytics_service.track_event(
                event_type="video_chat_ended",
                event_category="communication",
                event_action="end_session",
                context={
                    "session_id": session_id,
                    "duration": session.duration,
                    "user_agent": request.headers.get("User-Agent"),
                    "ip_address": request.remote_addr,
                },
            )
        except Exception as analytics_error:
            print(f"Analytics tracking failed: {analytics_error}")

        flash("Видео чат сесията е завършена.", "success")
        return redirect(url_for("video_chat"))

    # WebRTC Signaling API
    @app.route("/api/video_chat/signal/<session_id>", methods=["POST"])
    @login_required
    def video_chat_signal(session_id):
        """WebRTC signaling endpoint за обмен на сигнали между участниците"""
        from .models import VideoChatSession

        session = VideoChatSession.query.filter_by(session_id=session_id).first_or_404()

        # Проверяваме дали текущият потребител участва в сесията
        if (
            session.initiator_id != current_user.id
            and session.participant_id != current_user.id
        ):
            return {"error": "Unauthorized"}, 403

        data = request.get_json()
        if not data:
            return {"error": "No data provided"}, 400

        # Тук можем да съхраняваме сигнали в база данни или да ги предаваме чрез WebSocket
        # За опростеност връщаме success - в реално приложение ще има WebSocket сървър
        signal_type = data.get("type")

        # Track signaling event for analytics
        try:
            from ...analytics_service import analytics_service

            analytics_service.track_event(
                event_type="video_chat_signal",
                event_category="communication",
                event_action=signal_type,
                context={
                    "session_id": session_id,
                    "signal_type": signal_type,
                    "user_agent": request.headers.get("User-Agent"),
                    "ip_address": request.remote_addr,
                },
            )
        except Exception as analytics_error:
            print(f"Analytics tracking failed: {analytics_error}")

        return {"status": "signal_received", "type": signal_type}

    socketio.init_app(app, cors_allowed_origins="*")

    # SocketIO events
    @socketio.on("join")
    def on_join(data):
        room = data["room"]
        join_room(room)
        emit(
            "status",
            {"msg": f"{data['username']} се присъедини към {room}"},
            room=room,
        )
        analytics_service.track_event(
            "chat_join", "engagement", "join_room", {"room": room}
        )

    @socketio.on("leave")
    def on_leave(data):
        room = data["room"]
        leave_room(room)
        emit("status", {"msg": f"{data['username']} напусна {room}"}, room=room)

    @socketio.on("message")
    def handle_message(data):
        room = data["room"]
        username = data["username"]
        message = data["message"]
        file_path = data.get("file_path")

        # Запази в DB
        user = User.query.filter_by(username=username).first()
        chat_room = ChatRoom.query.filter_by(name=room).first()
        if not chat_room:
            chat_room = ChatRoom(name=room)
            db.session.add(chat_room)
            db.session.commit()

        msg = ChatMessage(
            room_id=chat_room.id,
            user_id=user.id,
            content=message,
            file_path=file_path,
        )
        db.session.add(msg)
        db.session.commit()

        emit(
            "message",
            {
                "username": username,
                "message": message,
                "file_path": file_path,
                "timestamp": str(msg.timestamp),
            },
            room=room,
        )
        analytics_service.track_event(
            "chat_message",
            "engagement",
            "send_message",
            {"room": room, "has_file": bool(file_path)},
        )

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

    @app.route("/volunteer_dashboard")
    @login_required
    def volunteer_dashboard():
        try:
            app.logger.info("Starting volunteer_dashboard function")
            # Check if user is volunteer
            if not current_user.is_volunteer:
                flash("Нямате достъп до доброволческия панел.", "error")
                return redirect(url_for("index"))

            app.logger.info(
                f"Volunteer found: {current_user.username} (id: {current_user.id})"
            )

            # Get real statistics from database
            try:
                from .models import Task, TaskPerformance

                # Completed tasks count
                completed_tasks = Task.query.filter_by(
                    assigned_to=current_user.id, status="completed"
                ).count()

                # Active tasks count (assigned but not completed)
                active_tasks_count = (
                    Task.query.filter_by(assigned_to=current_user.id)
                    .filter(Task.status.in_(["assigned", "in_progress"]))
                    .count()
                )

                # Average rating from performance records
                avg_rating_result = (
                    db.session.query(db.func.avg(TaskPerformance.quality_rating))
                    .filter_by(volunteer_id=current_user.id)
                    .scalar()
                )

                rating = round(avg_rating_result, 1) if avg_rating_result else 0.0

                # People helped count (unique tasks completed)
                people_helped = completed_tasks  # Approximation

                # Reviews count
                reviews_count = TaskPerformance.query.filter_by(
                    volunteer_id=current_user.id
                ).count()

            except Exception as e:
                app.logger.error(f"Error fetching volunteer stats: {e}")
                completed_tasks = 0
                active_tasks_count = 0
                rating = 0.0
                people_helped = 0
                reviews_count = 0

            # Get active tasks assigned to this volunteer
            try:
                # Get active tasks assigned to this volunteer
                active_tasks_query = (
                    Task.query.filter_by(assigned_to=current_user.id)
                    .filter(Task.status.in_(["assigned", "in_progress"]))
                    .order_by(Task.created_at.desc())
                    .limit(5)
                )

                active_tasks = []
                for task in active_tasks_query:
                    # Calculate progress based on status
                    if task.status == "assigned":
                        progress = 10
                    elif task.status == "in_progress":
                        progress = 50
                    else:
                        progress = 0

                    # Calculate time remaining (simplified)
                    time_remaining = "Няма краен срок"
                    if task.deadline:
                        from datetime import datetime

                        now = datetime.utcnow()
                        if task.deadline > now:
                            days_remaining = (task.deadline - now).days
                            if days_remaining == 0:
                                time_remaining = "Днес"
                            elif days_remaining == 1:
                                time_remaining = "1 ден"
                            elif days_remaining < 7:
                                time_remaining = f"{days_remaining} дни"
                            else:
                                time_remaining = f"{days_remaining // 7} седмици"
                        else:
                            time_remaining = "Просрочена"

                    active_tasks.append(
                        {
                            "id": task.id,
                            "title": task.title,
                            "location": task.location_text or "Не е посочена локация",
                            "date": (
                                task.created_at.strftime("%Y-%m-%d")
                                if task.created_at
                                else "Няма дата"
                            ),
                            "time_remaining": time_remaining,
                            "description": task.description or "Няма описание",
                            "priority": task.priority or "medium",
                            "progress": progress,
                        }
                    )

            except Exception as e:
                app.logger.error(f"Error fetching active tasks: {e}")
                active_tasks = []

            # Get available tasks count (open tasks not assigned)
            try:
                available_tasks_count = Task.query.filter_by(status="open").count()
            except Exception as e:
                app.logger.error(f"Error fetching available tasks count: {e}")
                available_tasks_count = 0

            # Get urgent tasks count (high priority open tasks)
            try:
                urgent_tasks_count = Task.query.filter_by(
                    status="open", priority="urgent"
                ).count()
            except Exception as e:
                app.logger.error(f"Error fetching urgent tasks count: {e}")
                urgent_tasks_count = 0

            # Prepare stats dictionary
            stats = {
                "completed_tasks": completed_tasks,
                "active_tasks": active_tasks_count,
                "rating": rating,
                "people_helped": people_helped,
                "reviews": reviews_count,
            }

            # Get gamification data
            gamification = {
                "points": getattr(current_user, "points", 0),
                "level": getattr(current_user, "level", 1),
                "experience": getattr(current_user, "experience", 0),
                "level_progress": (
                    getattr(current_user, "get_level_progress", lambda: 0)()
                    if hasattr(current_user, "get_level_progress")
                    else 0
                ),
                "next_level_exp": (
                    (getattr(current_user, "level", 1) * 100)
                    if hasattr(current_user, "level")
                    else 100
                ),  # Simple calculation
            }

            app.logger.info("Rendering template with volunteer data")
            return render_template(
                "volunteer_dashboard.html",
                current_user=current_user,
                stats=stats,
                active_tasks=active_tasks,
                available_tasks=available_tasks_count,
                urgent_tasks=urgent_tasks_count,
                gamification=gamification,
            )

        except Exception as e:
            app.logger.error(f"Error loading volunteer dashboard: {e}", exc_info=True)
            flash("Възникна грешка при зареждането на панела", "error")
            return redirect(url_for("index"))

    @app.route("/my_tasks", methods=["GET"], endpoint="my_tasks")
    @login_required
    def my_tasks():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for my tasks page
        return render_template("my_tasks.html")

    @app.route("/available_tasks", methods=["GET"], endpoint="available_tasks")
    @login_required
    def available_tasks():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for available tasks page
        return render_template("available_tasks.html")

    @app.route("/achievements", methods=["GET"], endpoint="achievements")
    @login_required
    def achievements():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for achievements page
        return render_template("achievements.html")

    @app.route("/volunteer_chat", methods=["GET"], endpoint="volunteer_chat")
    @login_required
    def volunteer_chat():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for volunteer chat page
        return render_template("volunteer_chat.html")

    @app.route("/volunteer_reports", methods=["GET"], endpoint="volunteer_reports")
    @login_required
    def volunteer_reports():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for volunteer reports page
        return render_template("volunteer_reports.html")

    @app.route(
        "/volunteer_settings", methods=["GET", "POST"], endpoint="volunteer_profile"
    )
    @login_required
    def volunteer_settings():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for volunteer settings page
        return render_template("volunteer_settings.html")

    @app.route("/leaderboard", methods=["GET"], endpoint="leaderboard")
    @login_required
    def leaderboard():
        if not current_user.is_volunteer:
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))
        # Placeholder for leaderboard page
        return render_template("leaderboard.html")

    @app.route("/volunteer_login", methods=["GET", "POST"])
    def volunteer_login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password) and user.is_volunteer:
                login_user(user)
                return redirect(url_for("volunteer_dashboard"))
            flash("Невалиден имейл или парола.", "error")
        return render_template("volunteer_login.html")

    @app.route("/admin_dashboard")
    @login_required
    def admin_dashboard():
        if not current_user.is_admin:
            flash("Нямате достъп до администраторския панел.", "error")
            return redirect(url_for("index"))
        # Placeholder for admin dashboard
        return render_template("admin_dashboard.html")

    @app.route("/volunteer_register", methods=["GET", "POST"])
    def volunteer_register():
        if request.method == "POST":
            data = request.form.to_dict()
            if User.query.filter_by(email=data.get("email")).first():
                flash("Имейлът вече е регистриран.", "error")
                return redirect(url_for("volunteer_register"))
            user = User(
                username=data.get("username"),
                email=data.get("email"),
                is_volunteer=True,
            )
            user.set_password(data.get("password"))
            db.session.add(user)
            db.session.commit()
            flash("Регистрацията е успешна! Можете да влезете.", "success")
            return redirect(url_for("volunteer_login"))
        return render_template("volunteer_register.html")

    return app


# (production: премахнати подробните before/after логове)


# създаваме default 'app' за тестове/локално стартиране
app = create_app(Config)


def init_sample_data():
    with app.app_context():
        from .models import Request, RequestLog, User

        db.create_all()  # Create tables if they exist

        # Check if users table is empty
        if User.query.count() == 0:
            # Create a sample user
            sample_user = User(
                username="testuser",
                email="test@example.com",
                is_volunteer=True,
                is_organization=False,
            )
            sample_user.set_password(os.getenv("SAMPLE_USER_PASSWORD", "password123"))
            db.session.add(sample_user)
            # Create admin user
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

        # Check if requests table is empty
        if Request.query.count() == 0:
            # Insert sample requests
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

            # Insert sample logs
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
