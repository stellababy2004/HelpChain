"""add ui_translation_freeze

Revision ID: 9d4e6f1a2b30
Revises: 8c3d5e7f9a01
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa


revision = "9d4e6f1a2b30"
down_revision = "8c3d5e7f9a01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ui_translation_freeze",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("release_tag", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("activated_by_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["activated_by_admin_user_id"], ["admin_users.id"]),
    )
    op.create_index("ix_ui_translation_freeze_activated_at", "ui_translation_freeze", ["activated_at"])
    op.create_index(
        "ix_ui_translation_freeze_activated_by_admin_user_id",
        "ui_translation_freeze",
        ["activated_by_admin_user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_ui_translation_freeze_activated_by_admin_user_id",
        table_name="ui_translation_freeze",
    )
    op.drop_index("ix_ui_translation_freeze_activated_at", table_name="ui_translation_freeze")
    op.drop_table("ui_translation_freeze")
