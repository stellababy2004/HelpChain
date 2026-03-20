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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ui_translation_events" not in tables:
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

    inspector = sa.inspect(bind)
    index_names = {idx["name"] for idx in inspector.get_indexes("ui_translation_events")}

    if "ix_ui_translation_events_translation_id" not in index_names:
        op.create_index(
            "ix_ui_translation_events_translation_id",
            "ui_translation_events",
            ["translation_id"],
            unique=False,
        )
    if "ix_ui_translation_events_locale" not in index_names:
        op.create_index(
            "ix_ui_translation_events_locale",
            "ui_translation_events",
            ["locale"],
            unique=False,
        )
    if "ix_ui_translation_events_key" not in index_names:
        op.create_index(
            "ix_ui_translation_events_key",
            "ui_translation_events",
            ["key"],
            unique=False,
        )
    if "ix_ui_translation_events_action" not in index_names:
        op.create_index(
            "ix_ui_translation_events_action",
            "ui_translation_events",
            ["action"],
            unique=False,
        )
    if "ix_ui_translation_events_actor_admin_user_id" not in index_names:
        op.create_index(
            "ix_ui_translation_events_actor_admin_user_id",
            "ui_translation_events",
            ["actor_admin_user_id"],
            unique=False,
        )
    if "ix_ui_translation_events_created_at" not in index_names:
        op.create_index(
            "ix_ui_translation_events_created_at",
            "ui_translation_events",
            ["created_at"],
            unique=False,
        )
    if "ix_ui_translation_events_locale_key_created_at" not in index_names:
        op.create_index(
            "ix_ui_translation_events_locale_key_created_at",
            "ui_translation_events",
            ["locale", "key", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    pass
