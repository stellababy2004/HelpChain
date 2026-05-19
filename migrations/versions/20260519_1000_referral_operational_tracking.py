"""add referral operational tracking fields

Revision ID: 20260519_1000
Revises: 20260519_0900
Create Date: 2026-05-19 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260519_1000"
down_revision = "20260519_0900"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return bool(inspect(bind).has_table(table_name))
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        return any(col.get("name") == column_name for col in inspect(bind).get_columns(table_name))
    except Exception:
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        return any(idx.get("name") == index_name for idx in inspect(bind).get_indexes(table_name))
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "case_referrals"):
        return

    columns = (
        ("operational_status", sa.Column("operational_status", sa.String(length=32), server_default="sent", nullable=False)),
        ("in_progress_at", sa.Column("in_progress_at", sa.DateTime(timezone=True), nullable=True)),
        ("completed_at", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)),
        ("suspended_at", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)),
        ("last_public_update_at", sa.Column("last_public_update_at", sa.DateTime(timezone=True), nullable=True)),
        ("public_status_note", sa.Column("public_status_note", sa.Text(), nullable=True)),
    )
    with op.batch_alter_table("case_referrals", schema=None) as batch_op:
        for column_name, column in columns:
            if not _has_column(bind, "case_referrals", column_name):
                batch_op.add_column(column)

    if not _has_index(bind, "case_referrals", "ix_case_referrals_operational_status"):
        op.create_index(
            "ix_case_referrals_operational_status",
            "case_referrals",
            ["operational_status"],
            unique=False,
        )

    try:
        bind.execute(
            text(
                "UPDATE case_referrals "
                "SET operational_status = COALESCE(NULLIF(operational_status, ''), status, 'sent')"
            )
        )
    except Exception:
        pass


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, "case_referrals"):
        return
    if _has_index(bind, "case_referrals", "ix_case_referrals_operational_status"):
        op.drop_index("ix_case_referrals_operational_status", table_name="case_referrals")

    with op.batch_alter_table("case_referrals", schema=None) as batch_op:
        for column_name in (
            "public_status_note",
            "last_public_update_at",
            "suspended_at",
            "completed_at",
            "in_progress_at",
            "operational_status",
        ):
            if _has_column(bind, "case_referrals", column_name):
                batch_op.drop_column(column_name)
