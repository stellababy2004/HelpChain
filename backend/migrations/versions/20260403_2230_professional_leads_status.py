"""ensure professional_leads.status exists and is backfilled

Revision ID: 20260403_2230
Revises: 20260301_1515
Create Date: 2026-04-03 22:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260403_2230"
down_revision = "20260301_1515"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    insp = inspect(bind)
    try:
        return table_name in insp.get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    insp = inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    insp = inspect(bind)
    try:
        indexes = insp.get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _has_table(bind, "professional_leads"):
        return

    if not _has_column(bind, "professional_leads", "status"):
        with op.batch_alter_table("professional_leads") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "status",
                    sa.String(length=30),
                    nullable=True,
                    server_default="new",
                )
            )

    if dialect == "postgresql":
        op.execute(
            "UPDATE professional_leads SET status='new' "
            "WHERE status IS NULL OR btrim(status) = ''"
        )
    else:
        op.execute(
            "UPDATE professional_leads SET status='new' "
            "WHERE status IS NULL OR trim(status) = ''"
        )

    with op.batch_alter_table("professional_leads") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            nullable=False,
            server_default=sa.text("'new'"),
        )

    if not _has_index(bind, "professional_leads", "ix_professional_leads_status"):
        op.create_index(
            "ix_professional_leads_status",
            "professional_leads",
            ["status"],
            unique=False,
        )


def downgrade():
    # Data-safe downgrade: keep the column once created/backfilled.
    pass
