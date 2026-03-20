"""add risk scoring fields to requests

Revision ID: 1a2b3c4d5e6f
Revises: 9d4e6f1a2b30
Create Date: 2026-03-07 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index


revision = "1a2b3c4d5e6f"
down_revision = "9d4e6f1a2b30"
branch_labels = None
depends_on = None


def table_exists(bind, table_name):
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def column_exists(bind, table_name, column_name):
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in cols


def index_exists(bind, table_name, index_name):
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    indexes = [idx.get("name") for idx in insp.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    bind = op.get_bind()

    if not table_exists(bind, "requests"):
        return

    if not column_exists(bind, "requests", "risk_score"):
        op.add_column(
            "requests",
            sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        )
    if not column_exists(bind, "requests", "risk_level"):
        op.add_column(
            "requests",
            sa.Column(
                "risk_level",
                sa.String(length=20),
                nullable=False,
                server_default="standard",
            ),
        )
    if not column_exists(bind, "requests", "risk_signals"):
        op.add_column("requests", sa.Column("risk_signals", sa.Text(), nullable=True))
    if not column_exists(bind, "requests", "risk_last_updated"):
        op.add_column(
            "requests",
            sa.Column("risk_last_updated", sa.DateTime(timezone=True), nullable=True),
        )
    if not index_exists(bind, "requests", "ix_requests_risk_level"):
        op.create_index(
            "ix_requests_risk_level", "requests", ["risk_level"], unique=False
        )


def downgrade():
    bind = op.get_bind()

    if not table_exists(bind, "requests"):
        return

    if index_exists(bind, "requests", "ix_requests_risk_level"):
        safe_drop_index(op, "ix_requests_risk_level", table_name="requests")
    if column_exists(bind, "requests", "risk_last_updated"):
        safe_drop_column(op, "requests", "risk_last_updated")
    if column_exists(bind, "requests", "risk_signals"):
        safe_drop_column(op, "requests", "risk_signals")
    if column_exists(bind, "requests", "risk_level"):
        safe_drop_column(op, "requests", "risk_level")
    if column_exists(bind, "requests", "risk_score"):
        safe_drop_column(op, "requests", "risk_score")