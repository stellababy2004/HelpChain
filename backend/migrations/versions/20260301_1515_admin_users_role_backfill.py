"""ensure admin_users.role exists and is backfilled

Revision ID: 20260301_1515
Revises: 20260301_1205
Create Date: 2026-03-01 15:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260301_1515"
down_revision = "20260301_1205"
branch_labels = None
depends_on = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    insp = inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _has_column(bind, "admin_users", "role"):
        op.add_column(
            "admin_users",
            sa.Column("role", sa.String(length=32), nullable=True),
        )

    # Backfill legacy/empty values to a safe operator tier.
    if dialect == "postgresql":
        op.execute(
            "UPDATE admin_users SET role='superadmin' "
            "WHERE role IS NULL OR btrim(role) = ''"
        )
    else:
        op.execute(
            "UPDATE admin_users SET role='superadmin' "
            "WHERE role IS NULL OR trim(role) = ''"
        )


def downgrade():
    # Data-safe downgrade: keep role column if present.
    pass

