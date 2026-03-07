"""add ui_translation_events

Revision ID: 8c3d5e7f9a01
Revises: 7b2c4d6e8f90
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa


revision = "8c3d5e7f9a01"
down_revision = "7b2c4d6e8f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ui_translation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translation_id", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="human"),
        sa.Column("actor_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("old_text", sa.Text(), nullable=True),
        sa.Column("new_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["translation_id"], ["ui_translations.id"]),
        sa.ForeignKeyConstraint(["actor_admin_user_id"], ["admin_users.id"]),
    )
    op.create_index("ix_ui_translation_events_translation_id", "ui_translation_events", ["translation_id"])
    op.create_index("ix_ui_translation_events_locale", "ui_translation_events", ["locale"])
    op.create_index("ix_ui_translation_events_key", "ui_translation_events", ["key"])
    op.create_index("ix_ui_translation_events_action", "ui_translation_events", ["action"])
    op.create_index("ix_ui_translation_events_actor_admin_user_id", "ui_translation_events", ["actor_admin_user_id"])
    op.create_index("ix_ui_translation_events_created_at", "ui_translation_events", ["created_at"])
    op.create_index(
        "ix_ui_translation_events_locale_key_created_at",
        "ui_translation_events",
        ["locale", "key", "created_at"],
    )


def downgrade():
    op.drop_index("ix_ui_translation_events_locale_key_created_at", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_created_at", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_actor_admin_user_id", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_action", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_key", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_locale", table_name="ui_translation_events")
    op.drop_index("ix_ui_translation_events_translation_id", table_name="ui_translation_events")
    op.drop_table("ui_translation_events")
