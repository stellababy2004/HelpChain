"""add admin user onboarding fields

Revision ID: 20260429_1100
Revises: 20260423_0930
Create Date: 2026-04-29 11:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260429_1100"
down_revision = "20260423_0930"
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


def upgrade():
    bind = op.get_bind()
    table_name = "admin_users"
    if not _has_table(bind, table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if not _has_column(bind, table_name, "must_change_password"):
            batch_op.add_column(
                sa.Column(
                    "must_change_password",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if not _has_column(bind, table_name, "onboarding_started_at"):
            batch_op.add_column(sa.Column("onboarding_started_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(bind, table_name, "onboarding_completed_at"):
            batch_op.add_column(sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column(bind, table_name, "onboarding_step"):
            batch_op.add_column(sa.Column("onboarding_step", sa.String(length=32), nullable=True))
        if not _has_column(bind, table_name, "onboarding_data_json"):
            batch_op.add_column(sa.Column("onboarding_data_json", sa.Text(), nullable=True))


def downgrade():
    # Data-safe downgrade: keep onboarding fields once provisioned.
    pass
