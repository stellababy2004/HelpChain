import sqlite3
import os

from werkzeug.security import check_password_hash

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()

cursor.execute(
    "SELECT username, password_hash FROM admin_users WHERE username = ?", ("admin",)
)
row = cursor.fetchone()
if row:
    username, password_hash = row
    print(f"Username: {username}")
    print(f"Password hash: {password_hash}")

    # Test-only password from env or safe placeholder fallback.
    test_password = os.getenv("TEST_ADMIN_PASSWORD", "test-password")
    is_valid = check_password_hash(password_hash, test_password)
    print(f"Password '{test_password}' valid: {is_valid}")

conn.close()

