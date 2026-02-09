from backend.helpchain_backend.src.app import create_app
from backend.helpchain_backend.src.extensions import db

app = create_app()
print("DB URI:", app.config.get("SQLALCHEMY_DATABASE_URI"))
print("Track mods:", app.config.get("SQLALCHEMY_TRACK_MODIFICATIONS"))
with app.app_context():
    eng = db.engine
    print("Engine:", eng)
    conn = eng.connect()
    try:
        res = conn.exec_driver_sql("SELECT 1").scalar()
        print("SELECT 1 ->", res)
    finally:
        conn.close()
print("OK")
