"""add risk scoring fields to requests

Revision ID: 1a2b3c4d5e6f
Revises: 9d4e6f1a2b30
Create Date: 2026-03-07 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e6f"
down_revision = "9d4e6f1a2b30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "requests",
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "requests",
        sa.Column(
            "risk_level",
            sa.String(length=20),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column("requests", sa.Column("risk_signals", sa.Text(), nullable=True))
    op.add_column(
        "requests", sa.Column("risk_last_updated", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_requests_risk_level", "requests", ["risk_level"], unique=False
    )


def downgrade():
    op.drop_index("ix_requests_risk_level", table_name="requests")
    op.drop_column("requests", "risk_last_updated")
    op.drop_column("requests", "risk_signals")
    op.drop_column("requests", "risk_level")
    op.drop_column("requests", "risk_score")
