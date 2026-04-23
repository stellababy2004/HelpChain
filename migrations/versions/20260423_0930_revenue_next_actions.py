"""add revenue next action fields

Revision ID: 20260423_0930
Revises: 20260422_1600
Create Date: 2026-04-23 09:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260423_0930"
down_revision = "20260422_1600"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        return any(
            col.get("name") == column_name
            for col in inspect(bind).get_columns(table_name)
        )
    except Exception:
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        return any(
            idx.get("name") == index_name
            for idx in inspect(bind).get_indexes(table_name)
        )
    except Exception:
        return False


def _add_next_action_fields(bind, table_name: str) -> None:
    if not _has_table(bind, table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if not _has_column(bind, table_name, "next_action_at"):
            batch_op.add_column(sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(bind, table_name, "next_action_note"):
            batch_op.add_column(sa.Column("next_action_note", sa.String(length=255), nullable=True))

    index_name = f"ix_{table_name}_next_action_at"
    if not _has_index(bind, table_name, index_name):
        op.create_index(index_name, table_name, ["next_action_at"], unique=False)


def upgrade():
    bind = op.get_bind()
    _add_next_action_fields(bind, "professional_leads")
    _add_next_action_fields(bind, "organization_access_requests")


def downgrade():
    # Data-safe downgrade: keep founder follow-up fields once created.
    pass
