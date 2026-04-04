"""add professional lead follow-up timestamps

Revision ID: 20260404_0915
Revises: 6d7c4c5f9a21
Create Date: 2026-04-04 09:15:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260404_0915"
down_revision = "6d7c4c5f9a21"
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
            batch_op.add_column(
                sa.Column("first_followup_sent_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.add_column(
                sa.Column("second_followup_sent_at", sa.DateTime(timezone=True), nullable=True)
            )
        return

    if not _has_table(bind, "professional_leads"):
        return

    with op.batch_alter_table("professional_leads") as batch_op:
        if not _has_column(bind, "professional_leads", "first_followup_sent_at"):
            batch_op.add_column(
                sa.Column("first_followup_sent_at", sa.DateTime(timezone=True), nullable=True)
            )
        if not _has_column(bind, "professional_leads", "second_followup_sent_at"):
            batch_op.add_column(
                sa.Column("second_followup_sent_at", sa.DateTime(timezone=True), nullable=True)
            )


def downgrade():
    # Data-safe downgrade: keep the columns once created.
    pass
