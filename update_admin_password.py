import sqlite3

from werkzeug.security import generate_password_hash

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()

# Update admin password
new_hash = generate_password_hash("admin123")
cursor.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (new_hash, "admin"))

conn.commit()
print("Admin password updated to 'admin123'")

# Verify
cursor.execute("SELECT username, password_hash FROM admin_users WHERE username = ?", ("admin",))
row = cursor.fetchone()
print(f"Admin user: {row}")

conn.close()
