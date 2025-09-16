from pathlib import Path
import json
from sqlalchemy import create_engine, text

DB = Path(__file__).resolve().parents[1] / "backend" / "instance" / "volunteers.db"
engine = create_engine(f"sqlite:///{DB.as_posix()}")

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT id, username, email, role, created_at FROM users")
    ).fetchall()
    data = [
        dict(r._mapping) for r in rows
    ]  # използваме ._mapping за съвместимост с всички версии
print(json.dumps(data, default=str, ensure_ascii=False, indent=2))
