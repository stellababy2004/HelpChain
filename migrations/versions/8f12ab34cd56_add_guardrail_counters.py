"""add guardrail counters

Revision ID: 8f12ab34cd56
Revises: d8a7c6b5e4f3
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "8f12ab34cd56"
down_revision = "d8a7c6b5e4f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guardrail_counters",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade():
    op.drop_table("guardrail_counters")
