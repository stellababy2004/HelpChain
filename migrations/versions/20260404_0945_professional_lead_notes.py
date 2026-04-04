"""ensure professional lead notes exists

Revision ID: 20260404_0945
Revises: 20260404_0915
Create Date: 2026-04-04 09:45:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260404_0945"
down_revision = "20260404_0915"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        insp = inspect(bind)
        cols = insp.get_columns(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(c.get("name") == column_name for c in cols)


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        with op.batch_alter_table("professional_leads") as batch_op:
            batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        return

    if not _has_table(bind, "professional_leads"):
        return

    if _has_column(bind, "professional_leads", "notes"):
        return

    with op.batch_alter_table("professional_leads") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade():
    # Data-safe downgrade: keep the column once created.
    pass
