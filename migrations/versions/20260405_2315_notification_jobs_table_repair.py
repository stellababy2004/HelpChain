"""repair missing notification_jobs table in production

Revision ID: 20260405_2315
Revises: 20260405_1305
Create Date: 2026-04-05 23:15:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260405_2315"
down_revision = "20260405_1305"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        insp = inspect(bind)
        indexes = insp.get_indexes(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        op.create_table(
            "notification_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("recipient", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("5"),
            ),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("structure_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_notification_jobs_channel",
            "notification_jobs",
            ["channel"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_created_at",
            "notification_jobs",
            ["created_at"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_event_type",
            "notification_jobs",
            ["event_type"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_next_retry_at",
            "notification_jobs",
            ["next_retry_at"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_recipient",
            "notification_jobs",
            ["recipient"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_status",
            "notification_jobs",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_status_next",
            "notification_jobs",
            ["status", "next_retry_at"],
            unique=False,
        )
        op.create_index(
            "ix_notification_jobs_structure_id",
            "notification_jobs",
            ["structure_id"],
            unique=False,
        )
        return

    if not _has_table(bind, "notification_jobs"):
        op.create_table(
            "notification_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("recipient", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("5"),
            ),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("structure_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_channel"):
        op.create_index(
            "ix_notification_jobs_channel",
            "notification_jobs",
            ["channel"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_created_at"):
        op.create_index(
            "ix_notification_jobs_created_at",
            "notification_jobs",
            ["created_at"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_event_type"):
        op.create_index(
            "ix_notification_jobs_event_type",
            "notification_jobs",
            ["event_type"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_next_retry_at"):
        op.create_index(
            "ix_notification_jobs_next_retry_at",
            "notification_jobs",
            ["next_retry_at"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_recipient"):
        op.create_index(
            "ix_notification_jobs_recipient",
            "notification_jobs",
            ["recipient"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_status"):
        op.create_index(
            "ix_notification_jobs_status",
            "notification_jobs",
            ["status"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_status_next"):
        op.create_index(
            "ix_notification_jobs_status_next",
            "notification_jobs",
            ["status", "next_retry_at"],
            unique=False,
        )
    if not _has_index(bind, "notification_jobs", "ix_notification_jobs_structure_id"):
        op.create_index(
            "ix_notification_jobs_structure_id",
            "notification_jobs",
            ["structure_id"],
            unique=False,
        )


def downgrade():
    # Data-safe downgrade: do not drop repaired notification_jobs table/indexes.
    pass
