import sys

sys.path.insert(0, "backend")
from appy import app, db
from sqlalchemy import text

with app.app_context():
    db.session.execute(
        text(
            "ALTER TABLE help_requests ADD COLUMN priority VARCHAR(50) DEFAULT 'normal' NOT NULL"
        )
    )
    db.session.commit()
    print("Added priority column to help_requests table")
