from pathlib import Path
from sqlalchemy import create_engine, text

DB = Path(__file__).resolve().parents[1] / "backend" / "instance" / "volunteers.db"
engine = create_engine(f"sqlite:///{DB.as_posix()}")

EMAIL = "san4o_baby@hotmail.com"

with engine.begin() as conn:  # използва транзакция и автокомит при успешно изпълнение
    conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": EMAIL})
    print("deleted", EMAIL)