import sqlite3

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

    # Test password
    test_password = "admin123"  # pragma: allowlist secret
    is_valid = check_password_hash(password_hash, test_password)
    print(f"Password 'admin123' valid: {is_valid}")

conn.close()
