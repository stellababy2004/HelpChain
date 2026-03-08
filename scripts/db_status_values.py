import os
import sys
from urllib.parse import urlparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from backend.local_db_guard import CANONICAL_DB_URI, is_canonical_db_uri

default_sqlite = CANONICAL_DB_URI
db_url = (
    os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL") or default_sqlite
)
print("APP: backend.appy:app")
print("DB:", db_url)
if not is_canonical_db_uri(db_url):
    print("WARNING: non-canonical DB target detected.")
    print("EXPECTED:", CANONICAL_DB_URI)
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
