"""add notification_jobs table

Revision ID: b7c8d9e0f1a2
Revises: f1b2c3d4e5f6
Create Date: 2026-03-13 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index


revision = "b7c8d9e0f1a2"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notification_jobs" in set(inspector.get_table_names()):
        return

    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, index=True),
        sa.Column("event_type", sa.String(length=64), nullable=False, index=True),
        sa.Column("recipient", sa.String(length=255), nullable=False, index=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("structure_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
    )

    op.create_index(
        "ix_notification_jobs_status_next",
        "notification_jobs",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notification_jobs" not in set(inspector.get_table_names()):
        return
    safe_drop_index(op, "ix_notification_jobs_status_next", table_name="notification_jobs")
    op.drop_table("notification_jobs")