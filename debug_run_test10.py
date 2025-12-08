import os
import sys

from flask import Flask

# ensure backend dir is on path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["HELPCHAIN_TEST_DEBUG"] = "1"

from backend.extensions import db

# Import models similar to test
try:
    from models_with_analytics import NotificationPreference, NotificationTemplate, PushSubscription, Task, TaskAssignment, TaskPerformance, User
except Exception:
    from models import NotificationPreference, NotificationTemplate, PushSubscription, User

print("Imported User from module:", User.__module__)

app = Flask(__name__)
app.config["TESTING"] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from routes.notifications import notification_bp

# init db
db.init_app(app)
app.register_blueprint(notification_bp, url_prefix="/api/notification")

with app.app_context():
    db.create_all()
    print("db.engine:", getattr(db, "engine", None))
    print("db.session id:", id(db.session))
    # show whether User has query attribute
    print("User attr query:", getattr(User, "query", None))
    try:
        print("User.query type:", type(User.query))
    except Exception as e:
        print("User.query access raised:", e)

    u = User(username="test_user", email="t@e.com", password_hash="x")
    db.session.add(u)
    db.session.flush()
    print("after flush user id:", getattr(u, "id", None))
    db.session.commit()

    # raw select using session
    try:
        res = db.session.query(User).filter_by(username="test_user").all()
        print("session.query(User).all():", res)
    except Exception as e:
        import traceback

        traceback.print_exc()

    try:
        res2 = User.query.filter_by(username="test_user").all()
        print("User.query.all():", res2)
    except Exception as e:
        import traceback

        traceback.print_exc()

print("done")
