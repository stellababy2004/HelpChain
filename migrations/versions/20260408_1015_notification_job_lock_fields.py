"""add notification_jobs lock and processed timestamps

Revision ID: 20260408_1015
Revises: 20260406_0100
Create Date: 2026-04-08 10:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260408_1015"
down_revision = "20260406_0100"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        cols = inspect(bind).get_columns(table_name)
    except Exception:
        return False
    return any(col.get("name") == column_name for col in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspect(bind).get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "notification_jobs"):
        return

    if not _has_column(bind, "notification_jobs", "locked_at"):
        op.add_column(
            "notification_jobs",
            sa.Column("locked_at", sa.DateTime(), nullable=True),
        )
    if not _has_column(bind, "notification_jobs", "processed_at"):
        op.add_column(
            "notification_jobs",
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )

    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_locked_at"):
        op.create_index(
            "ix_notification_jobs_locked_at",
            "notification_jobs",
            ["locked_at"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_processed_at"):
        op.create_index(
            "ix_notification_jobs_processed_at",
            "notification_jobs",
            ["processed_at"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, "notification_jobs"):
        return

    if _has_index(bind, "notification_jobs", "ix_notification_jobs_processed_at"):
        op.drop_index(
            "ix_notification_jobs_processed_at",
            table_name="notification_jobs",
        )
    if _has_index(bind, "notification_jobs", "ix_notification_jobs_locked_at"):
        op.drop_index(
            "ix_notification_jobs_locked_at",
            table_name="notification_jobs",
        )

    if _has_column(bind, "notification_jobs", "processed_at"):
        op.drop_column("notification_jobs", "processed_at")
    if _has_column(bind, "notification_jobs", "locked_at"):
        op.drop_column("notification_jobs", "locked_at")
