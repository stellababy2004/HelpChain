import sqlite3
import sys
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "instance" / "volunteers.db"
if not db_path.exists():
    print(f"DB not found: {db_path}")
    sys.exit(2)
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rows = [r[0] for r in cur.fetchall()]
print("\n".join(rows))
conn.close()
