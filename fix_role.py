import sqlite3

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()
cursor.execute("UPDATE admin_users SET role = 'MODERATOR' WHERE role = 'moderator'")
conn.commit()
conn.close()
print("Updated role values")
