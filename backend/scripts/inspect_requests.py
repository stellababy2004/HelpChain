import os
import sys

HERE = os.path.dirname(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from backend.models import Request

from appy import app, db

with app.app_context():
    # ensure fresh DB
    db.drop_all()
    db.create_all()
    r1 = Request(name="Test1", email="t1@example.com", status="pending")
    r2 = Request(name="Test2", email="t2@example.com", status="completed")
    db.session.add_all([r1, r2])
    db.session.commit()

    client = app.test_client()
    # set admin session
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_user_id"] = 1
        sess["admin_username"] = "tester"
        sess["user_id"] = 1
    resp = client.get("/admin/api/requests?status=pending")
    print("status", resp.status_code)
    try:
        print("json:", resp.get_json())
    except Exception:
        print("text:", resp.get_data()[:500])
