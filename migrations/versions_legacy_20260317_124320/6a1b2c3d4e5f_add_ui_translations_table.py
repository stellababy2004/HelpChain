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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = inspector.get_table_names()

    if "ui_translations" not in tables:
        op.create_table(
            "ui_translations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("locale", sa.String(length=16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("key", "locale", name="uq_ui_translations_key_locale"),
        )


def downgrade() -> None:
    pass
