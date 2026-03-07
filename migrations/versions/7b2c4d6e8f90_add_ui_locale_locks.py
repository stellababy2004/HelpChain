"""add ui_locale_locks

Revision ID: 7b2c4d6e8f90
Revises: 6a1b2c3d4e5f
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa


revision = "7b2c4d6e8f90"
down_revision = "6a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ui_locale_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["locked_by_admin_user_id"], ["admin_users.id"]),
        sa.UniqueConstraint("locale", name="uq_ui_locale_locks_locale"),
    )
    op.create_index("ix_ui_locale_locks_locale", "ui_locale_locks", ["locale"])
    op.create_index("ix_ui_locale_locks_locked_at", "ui_locale_locks", ["locked_at"])
    op.create_index(
        "ix_ui_locale_locks_locked_by_admin_user_id",
        "ui_locale_locks",
        ["locked_by_admin_user_id"],
    )
    op.create_index("ix_ui_locale_locks_created_at", "ui_locale_locks", ["created_at"])


def downgrade():
    op.drop_index("ix_ui_locale_locks_created_at", table_name="ui_locale_locks")
    op.drop_index("ix_ui_locale_locks_locked_by_admin_user_id", table_name="ui_locale_locks")
    op.drop_index("ix_ui_locale_locks_locked_at", table_name="ui_locale_locks")
    op.drop_index("ix_ui_locale_locks_locale", table_name="ui_locale_locks")
    op.drop_table("ui_locale_locks")
