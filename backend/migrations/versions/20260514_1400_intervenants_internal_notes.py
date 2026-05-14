"""add internal notes to intervenants

Revision ID: 20260514_1400
Revises: 20260428_1625
Create Date: 2026-05-14 14:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260514_1400"
down_revision = "20260428_1625"
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
    if _has_column(bind, "intervenants", "internal_notes"):
        return

    with op.batch_alter_table("intervenants") as batch_op:
        batch_op.add_column(sa.Column("internal_notes", sa.Text(), nullable=True))


def downgrade():
    # Data-safe downgrade: keep operational notes once populated.
    pass
