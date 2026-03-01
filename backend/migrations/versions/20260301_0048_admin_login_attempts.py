"""add admin_login_attempts table for brute-force protection

Revision ID: 20260301_0048
Revises:
Create Date: 2026-03-01 00:48:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_0048"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
    )
    op.create_index(
        "ix_admin_login_attempts_ip", "admin_login_attempts", ["ip"], unique=False
    )
    op.create_index(
        "ix_admin_login_attempts_username",
        "admin_login_attempts",
        ["username"],
        unique=False,
    )
    op.create_index(
        "ix_admin_login_attempts_created_at",
        "admin_login_attempts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_login_attempts_ip_username_created_at",
        "admin_login_attempts",
        ["ip", "username", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_admin_login_attempts_ip_username_created_at",
        table_name="admin_login_attempts",
    )
    op.drop_index("ix_admin_login_attempts_created_at", table_name="admin_login_attempts")
    op.drop_index("ix_admin_login_attempts_username", table_name="admin_login_attempts")
    op.drop_index("ix_admin_login_attempts_ip", table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")

