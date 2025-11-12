"""Add role column to admin_users

Revision ID: add_admin_users_role_column
Revises: 25b31e8d0218
Create Date: 2025-11-12 08:55:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_admin_users_role_column"
down_revision = "25b31e8d0218"
branch_labels = None
depends_on = None


def upgrade():
    # Guard enums for non-postgres (render as VARCHAR) to avoid CREATE TYPE on SQLite
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        _sa_Enum = sa.Enum

        def _enum(*args, **kwargs):
            kwargs.setdefault("native_enum", False)
            return _sa_Enum(*args, **kwargs)

        sa.Enum = _enum
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if "admin_users" not in existing_tables:
        # Nothing to migrate here if table doesn't exist in this DB; another migration will create it.
        return

    existing_cols = {c["name"] for c in inspector.get_columns("admin_users")}

    def add_if_missing(col_name, column):
        if col_name not in existing_cols:
            op.add_column("admin_users", column)

    # Add role enum (nullable) if missing
    add_if_missing(
        "role",
        sa.Column(
            "role",
            sa.Enum("SUPER_ADMIN", "ADMIN", "MODERATOR", name="adminrole"),
            nullable=True,
        ),
    )

    # Add other admin fields that models expect
    add_if_missing("backup_codes", sa.Column("backup_codes", sa.Text(), nullable=True))
    add_if_missing(
        "two_factor_enabled",
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=True),
    )
    add_if_missing(
        "twofa_enabled", sa.Column("twofa_enabled", sa.Boolean(), nullable=True)
    )
    add_if_missing("last_login", sa.Column("last_login", sa.DateTime(), nullable=True))
    add_if_missing("is_active", sa.Column("is_active", sa.Boolean(), nullable=True))
    add_if_missing(
        "failed_login_attempts",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=True),
    )
    add_if_missing(
        "locked_until", sa.Column("locked_until", sa.DateTime(), nullable=True)
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = (
        [c["name"] for c in inspector.get_columns("admin_users")]
        if "admin_users" in inspector.get_table_names()
        else []
    )
    with op.batch_alter_table("admin_users") as batch_op:
        for col in (
            "locked_until",
            "failed_login_attempts",
            "is_active",
            "last_login",
            "twofa_enabled",
            "two_factor_enabled",
            "backup_codes",
            "role",
        ):
            if col in cols:
                try:
                    batch_op.drop_column(col)
                except Exception:
                    # SQLite may not support dropping columns cleanly; best-effort
                    pass
    # Note: do not drop the enum type here because it may be shared; cleanup if necessary in a postgres-only downgrade
