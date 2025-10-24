#!/usr/bin/env python3
"""
Migration script to add is_active column to volunteers table
"""
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from appy import app  # Import the Flask app directly
from models import Volunteer, db


def add_is_active_column():
    """Add is_active column to volunteers table"""
    with app.app_context():
        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [col["name"] for col in inspector.get_columns("volunteers")]

            if "is_active" not in columns:
                print("Adding is_active column to volunteers table...")

                # Add the column with default value True for existing records
                with db.engine.connect() as conn:
                    # For SQLite, we need to recreate the table
                    conn.execute(
                        db.text(
                            """
                        ALTER TABLE volunteers ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL
                    """
                        )
                    )
                    conn.commit()

                print("Successfully added is_active column!")
            else:
                print("is_active column already exists.")

        except Exception as e:
            print(f"Error adding column: {e}")
            return False

    return True


if __name__ == "__main__":
    success = add_is_active_column()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1)
