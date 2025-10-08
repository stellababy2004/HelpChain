import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,  # Add flash
)
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.utils import secure_filename
from .routes.api import api_bp
from .config import Config
from .extensions import db, babel, mail, migrate
from flask_babel import get_locale


import datetime  # Add this import

from .controllers.helpchain_controller import HelpChainController  # Add this import
from .models import Request, RequestLog, Volunteer, Feedback, User  # Add this import


controller = HelpChainController()  # Add this

login_manager = LoginManager()


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
    try:
        migrate.init_app(app, db)
    except Exception:
        # ignore if migrate not configured or already initialized
        pass

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
            sample_user.set_password("password123")
            db.session.add(sample_user)
            # Create admin user
            admin_user = User(
                username="admin",
                email="admin@example.com",
                is_volunteer=True,
                is_organization=False,
                is_admin=True,
            )
            admin_user.set_password("admin123")
            db.session.add(admin_user)
            db.session.commit()
            print("Sample user created: email=test@example.com, password=password123")
            print("Admin user created: email=admin@example.com, password=admin123")

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
    app.register_blueprint(api_bp, url_prefix="/api")

    # Регистрираме analytics blueprint (pages + api + stream)
    try:
        from .routes.analytics import analytics_bp

        app.register_blueprint(analytics_bp)
    except Exception as e:
        app.logger.info("analytics blueprint not loaded: %s", e)

    # Ако няма index шаблон/маршрут в appy, осигуряваме прост home route
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/set_language", methods=["POST"])
    def set_language():
        lang = request.form.get("language", "bg")
        resp = redirect(request.referrer or url_for("index"))
        resp.set_cookie("language", lang, max_age=30 * 24 * 3600)
        return resp

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
        # For now, just print the email
        print(
            f"New request submitted: ID {req.id}, Name: {req.name}, Email: {req.email}"
        )
        # TODO: Implement actual email sending with Flask-Mail

    @app.route("/admin", methods=["GET"])
    @login_required
    def admin_panel():
        if not current_user.is_admin:
            flash("Нямате достъп до админ панела.", "error")
            return redirect(url_for("dashboard"))
        from .models import Request, RequestLog, Volunteer

        requests = Request.query.all()
        logs = RequestLog.query.all()
        volunteers = Volunteer.query.all()
        logs_dict = {}
        for log in logs:
            if log.request_id not in logs_dict:
                logs_dict[log.request_id] = []
            logs_dict[log.request_id].append(log)
        print(
            f"Requests: {len(requests)}, Logs: {len(logs)}, Volunteers: {len(volunteers)}"
        )  # Debug log
        # Convert requests to list of dict for JSON serialization
        requests_dict = [
            {
                "id": r.id,
                "name": r.name,
                "phone": r.phone,
                "email": r.email,
                "location": r.location,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                "urgency": r.urgency,
            }
            for r in requests
        ]
        # Convert volunteers to list of dict for JSON serialization
        volunteers_dict = [
            {
                "id": v.id,
                "name": v.name,
                "email": v.email,
                "phone": v.phone,
                "location": v.location,
                "skills": v.skills,
            }
            for v in volunteers
        ]
        return render_template(
            "admin_dashboard.html",
            requests={"items": requests},
            logs_dict=logs_dict,
            requests_json=requests_dict,
            volunteers=volunteers,
            volunteers_json=volunteers_dict,
        )

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/become_volunteer", methods=["GET", "POST"])
    def become_volunteer():
        if request.method == "POST":
            data = request.form.to_dict()
            print(f"Received volunteer data: {data}")  # Debug log
            try:
                volunteer = Volunteer(
                    name=data.get("name"),
                    email=data.get("email"),
                    phone=data.get("phone"),
                    skills=data.get("skills"),
                    location=data.get("location"),
                )
                db.session.add(volunteer)
                db.session.commit()
                flash(
                    "Благодарим ви че се записахте като доброволец! Ще се свържем с вас скоро.",
                    "success",
                )
                return redirect(url_for("index"))
            except Exception as e:
                print(f"Error in become_volunteer: {e}")  # Debug log
                flash(f"Грешка при записване като доброволец: {str(e)}", "error")
                return redirect(url_for("become_volunteer"))
        return render_template("become_volunteer.html")

    @app.route("/feedback", methods=["POST"])
    def feedback():
        data = request.form.to_dict()
        print(f"Received feedback: {data}")  # Debug log
        try:
            feedback_entry = Feedback(
                name=data.get("name"),
                email=data.get("email"),
                message=data.get("message"),
            )
            db.session.add(feedback_entry)
            db.session.commit()
            flash("Благодарим ви за обратната връзка!", "success")
            return redirect(url_for("about"))
        except Exception as e:
            print(f"Error in feedback: {e}")  # Debug log
            flash(f"Грешка при изпращане на обратна връзка: {str(e)}", "error")
            return redirect(url_for("about"))

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

    # (production: премахнати подробните before/after логове)

    return app


# създаваме default 'app' за тестове/локално стартиране
app = create_app(Config)


def init_sample_data():
    with app.app_context():
        from .models import Request, RequestLog, User

        db.create_all()  # Create tables if they don't exist

        # Check if users table is empty
        if User.query.count() == 0:
            # Create a sample user
            sample_user = User(
                username="testuser",
                email="test@example.com",
                is_volunteer=True,
                is_organization=False,
            )
            sample_user.set_password("password123")
            db.session.add(sample_user)
            # Create admin user
            admin_user = User(
                username="admin",
                email="admin@example.com",
                is_volunteer=True,
                is_organization=False,
                is_admin=True,
            )
            admin_user.set_password("admin123")
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
