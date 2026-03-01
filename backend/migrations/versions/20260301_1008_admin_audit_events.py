"""add admin_audit_events table

Revision ID: 20260301_1008
Revises: 20260301_0048
Create Date: 2026-03-01 10:08:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_1008"
down_revision = "20260301_0048"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("admin_username", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_admin_audit_events_created_at", "admin_audit_events", ["created_at"], unique=False
    )
    op.create_index(
        "ix_admin_audit_events_action", "admin_audit_events", ["action"], unique=False
    )
    op.create_index(
        "ix_admin_audit_events_admin_user_id",
        "admin_audit_events",
        ["admin_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_events_target_type_target_id_created_at",
        "admin_audit_events",
        ["target_type", "target_id", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_admin_audit_events_target_type_target_id_created_at",
        table_name="admin_audit_events",
    )
    op.drop_index("ix_admin_audit_events_admin_user_id", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_action", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_created_at", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")

