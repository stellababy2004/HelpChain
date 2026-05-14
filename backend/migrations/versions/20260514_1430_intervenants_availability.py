"""add availability to intervenants

Revision ID: 20260514_1430
Revises: 20260514_1400
Create Date: 2026-05-14 14:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260514_1430"
down_revision = "20260514_1400"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    insp = inspect(bind)
    try:
        return table_name in insp.get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    insp = inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "intervenants"):
        return
    if _has_column(bind, "intervenants", "availability"):
        return

    with op.batch_alter_table("intervenants") as batch_op:
        batch_op.add_column(sa.Column("availability", sa.String(length=32), nullable=True))


def downgrade():
    # Data-safe downgrade: keep operational availability once populated.
    pass
