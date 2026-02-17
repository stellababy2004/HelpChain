import os
import sys
from urllib.parse import urlparse

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
default_sqlite = f"sqlite:///{os.path.join(root, 'instance', 'app.db')}"
db_url = (
    os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL") or default_sqlite
)
print("Using DB URL:", db_url)
parsed = urlparse(db_url)
if parsed.scheme.startswith("sqlite"):
    # get path
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
    elif db_url.startswith("sqlite://"):
        path = db_url.replace("sqlite://", "")
    else:
        path = parsed.path
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print("DB file not found at", path)
        sys.exit(1)
    import sqlite3

    conn = sqlite3.connect(path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT status FROM requests")
        rows = cur.fetchall()
        print("Distinct status values in requests:")
        for r in rows:
            print("-", r[0])
    except Exception as e:
        print("Error querying requests table:", e)
    finally:
        conn.close()
else:
    print("Non-sqlite DB detected; please run an equivalent query on your Postgres DB:")
    print("SELECT DISTINCT status FROM requests;")
