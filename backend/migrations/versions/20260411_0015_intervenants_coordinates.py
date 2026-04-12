"""add latitude/longitude to intervenants

Revision ID: 20260411_0015
Revises: 20260403_2230
Create Date: 2026-04-11 00:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260411_0015"
down_revision = "20260403_2230"
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

    with op.batch_alter_table("intervenants") as batch_op:
        if not _has_column(bind, "intervenants", "latitude"):
            batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        if not _has_column(bind, "intervenants", "longitude"):
            batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))


def downgrade():
    # Data-safe downgrade: keep columns once populated.
    pass
