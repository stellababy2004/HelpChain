"""add ui_translations table

Revision ID: 6a1b2c3d4e5f
Revises: 3eb5b88949ff
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa


revision = "6a1b2c3d4e5f"
down_revision = "3eb5b88949ff"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ui_translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", "locale", name="uq_ui_translations_key_locale"),
    )
    op.create_index("ix_ui_translations_key", "ui_translations", ["key"])
    op.create_index("ix_ui_translations_locale", "ui_translations", ["locale"])
    op.create_index("ix_ui_translations_created_at", "ui_translations", ["created_at"])
    op.create_index("ix_ui_translations_locale_key", "ui_translations", ["locale", "key"])


def downgrade():
    op.drop_index("ix_ui_translations_locale_key", table_name="ui_translations")
    op.drop_index("ix_ui_translations_created_at", table_name="ui_translations")
    op.drop_index("ix_ui_translations_locale", table_name="ui_translations")
    op.drop_index("ix_ui_translations_key", table_name="ui_translations")
    op.drop_table("ui_translations")

