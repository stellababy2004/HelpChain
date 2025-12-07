#!/usr/bin/env python3
"""
PostgreSQL deployment setup script for HelpChain
"""

import os
import subprocess
import sys
from pathlib import Path


def setup_postgresql_deployment():
    """Setup PostgreSQL database and run migrations"""

    print("🚀 HelpChain PostgreSQL Deployment Setup")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("alembic.ini").exists():
        print("❌ Error: alembic.ini not found. Run this script from the project root.")
        return False

    # Check environment variables
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("⚠️  Warning: DATABASE_URL not set. Using default PostgreSQL connection.")
        db_url = "postgresql://helpchain_user:helpchain_pass@localhost:5432/helpchain_db"

    print(f"📊 Database URL: {db_url.replace(db_url.split('@')[0].split(':')[-1], '***')}")

    # Set Alembic configuration
    os.environ["ALEMBIC_CONFIG"] = str(Path("alembic.ini").absolute())

    try:
        # Step 1: Initialize database (create if not exists)
        print("\n📋 Step 1: Checking database connection...")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import os
os.environ['DATABASE_URL'] = '{db_url}'
from sqlalchemy import create_engine, text
engine = create_engine('{db_url}')
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    version = result.fetchone()[0]
    print("✅ PostgreSQL connected successfully")
    print(f"📊 Version: {{version[:50]}}...")
""",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode != 0:
            print("❌ Database connection failed:")
            print(result.stderr)
            return False

        print(result.stdout.strip())

        # Step 2: Run Alembic migrations
        print("\n📋 Step 2: Running database migrations...")

        # First, stamp the database with the initial revision if needed
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=".",
            env={**os.environ, "DATABASE_URL": db_url},
        )

        if "head" not in result.stdout and "001_initial" not in result.stdout:
            print("📝 Stamping database with initial revision...")
            result = subprocess.run(
                ["alembic", "stamp", "001_initial"],
                capture_output=True,
                text=True,
                cwd=".",
                env={**os.environ, "DATABASE_URL": db_url},
            )

            if result.returncode != 0:
                print("❌ Failed to stamp database:")
                print(result.stderr)
                return False

        # Run upgrade to latest
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=".",
            env={**os.environ, "DATABASE_URL": db_url},
        )

        if result.returncode != 0:
            print("❌ Migration failed:")
            print(result.stderr)
            return False

        print("✅ Migrations completed successfully")
        print(result.stdout.strip())

        # Step 3: Verify database setup
        print("\n📋 Step 3: Verifying database setup...")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import os
os.environ['DATABASE_URL'] = '{db_url}'
from sqlalchemy import create_engine, text, inspect

engine = create_engine('{db_url}')
inspector = inspect(engine)

print("📊 Created tables:")
tables = ['users', 'admin_users', 'volunteers', 'help_requests', 'notifications', 'user_activities']
for table in tables:
    if inspector.has_table(table):
        columns = [col['name'] for col in inspector.get_columns(table)]
        print("  ✅ %s: %d columns" % (table, len(columns)))
    else:
        print("  ❌ %s: missing" % table)

print("\\n🎯 Database setup verification complete")
""",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode != 0:
            print("❌ Database verification failed:")
            print(result.stderr)
            return False

        print(result.stdout.strip())

        # Step 4: Initialize default data
        print("\n📋 Step 4: Initializing default data...")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import os
import sys
sys.path.insert(0, 'backend')
os.environ['DATABASE_URL'] = '{db_url}'

from appy import app
with app.app_context():
    try:
        # Initialize default admin user
            from models import AdminUser
        admin = AdminUser.query.filter_by(username='admin').first()
        if not admin:
            admin = AdminUser(username='admin')
            admin.set_password('Admin123')
            from backend.extensions import db
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin user created (admin/Admin123)")
        else:
            print("✅ Default admin user already exists")

        # Initialize default roles and permissions
        from models import Role, Permission, RolePermission
        if not Role.query.filter_by(name='admin').first():
            admin_role = Role(name='admin', description='Administrator role', is_system_role=True)
            db.session.add(admin_role)
            db.session.commit()
            print("✅ Default admin role created")
        else:
            print("✅ Default admin role already exists")

        print("🎯 Default data initialization complete")

    except Exception as e:
        print("❌ Error initializing default data: %s" % e)
        import traceback
        traceback.print_exc()
""",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode != 0:
            print("❌ Default data initialization failed:")
            print(result.stderr)
            return False

        print(result.stdout.strip())

        print("\n🎉 PostgreSQL deployment setup completed successfully!")
        print("\n📝 Next steps:")
        print("  1. Set DATABASE_URL environment variable in production")
        print("  2. Configure PostgreSQL connection pooling if needed")
        print("  3. Set up database backups")
        print("  4. Monitor database performance")

        return True

    except Exception as e:
        print(f"❌ Unexpected error during deployment: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = setup_postgresql_deployment()
    sys.exit(0 if success else 1)
