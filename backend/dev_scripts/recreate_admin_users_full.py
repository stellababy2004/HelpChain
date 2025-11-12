import sqlite3

p = r"C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\instance\volunteers.db"
con = sqlite3.connect(p)
c = con.cursor()
try:
    # Drop existing admin_users (if present)
    c.execute("DROP TABLE IF EXISTS admin_users")
    # Create admin_users with full schema matching backend migration
    c.execute(
        """
    CREATE TABLE admin_users (
        id INTEGER PRIMARY KEY,
        username VARCHAR(64),
        email VARCHAR(120),
        password_hash VARCHAR(128),
        role VARCHAR(32),
        twofa_secret VARCHAR(32),
        backup_codes TEXT,
        two_factor_enabled BOOLEAN,
        created_at DATETIME,
        updated_at DATETIME,
        last_login DATETIME,
        is_active BOOLEAN,
        failed_login_attempts INTEGER,
        locked_until DATETIME
    )
    """
    )
    con.commit()
    print("admin_users recreated with full schema")
except Exception as e:
    print("error", e)
finally:
    con.close()
