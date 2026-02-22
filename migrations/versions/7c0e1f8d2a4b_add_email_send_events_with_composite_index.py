"""add email_send_events with composite index

Revision ID: 7c0e1f8d2a4b
Revises: 9f1d4d7d2e1a
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c0e1f8d2a4b"
down_revision = "9f1d4d7d2e1a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_send_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ua", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_send_events_created_at",
        "email_send_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_events_email_hash",
        "email_send_events",
        ["email_hash"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_events_purpose",
        "email_send_events",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_events_hash_purpose_created",
        "email_send_events",
        ["email_hash", "purpose", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_email_send_events_hash_purpose_created",
        table_name="email_send_events",
    )
    op.drop_index("ix_email_send_events_purpose", table_name="email_send_events")
    op.drop_index("ix_email_send_events_email_hash", table_name="email_send_events")
    op.drop_index("ix_email_send_events_created_at", table_name="email_send_events")
    op.drop_table("email_send_events")

