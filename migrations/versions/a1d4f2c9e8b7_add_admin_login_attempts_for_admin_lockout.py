"""add admin_login_attempts table for admin lockout flow

Revision ID: a1d4f2c9e8b7
Revises: 8f12ab34cd56
Create Date: 2026-03-02 12:55:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1d4f2c9e8b7"
down_revision = "8f12ab34cd56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "admin_login_attempts" in existing_tables:
        return

    op.create_table(
        "admin_login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
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


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "admin_login_attempts" not in existing_tables:
        return

    for idx in (
        "ix_admin_login_attempts_ip_username_created_at",
        "ix_admin_login_attempts_created_at",
        "ix_admin_login_attempts_username",
        "ix_admin_login_attempts_ip",
    ):
        op.drop_index(idx, table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")
