"""Link identified sales prospects to analytics visitors.

Revision ID: 20261006_1300
Revises: 20261006_1200
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261006_1300"
down_revision = "20261006_1200"
branch_labels = None
depends_on = None


def _columns(bind, table_name: str) -> set[str]:
    try:
        return {column["name"] for column in inspect(bind).get_columns(table_name)}
    except Exception:
        return set()


def _indexes(bind, table_name: str) -> set[str]:
    try:
        return {index["name"] for index in inspect(bind).get_indexes(table_name)}
    except Exception:
        return set()


def upgrade():
    bind = op.get_bind()

    for table_name in ("professional_leads", "organization_access_requests"):
        if "visitor_id" not in _columns(bind, table_name):
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(
                    sa.Column("visitor_id", sa.String(length=128), nullable=True)
                )

        index_name = f"ix_{table_name}_visitor_id"
        if index_name not in _indexes(bind, table_name):
            op.create_index(
                index_name,
                table_name,
                ["visitor_id"],
                unique=False,
            )


def downgrade():
    bind = op.get_bind()

    for table_name in ("professional_leads", "organization_access_requests"):
        index_name = f"ix_{table_name}_visitor_id"

        if index_name in _indexes(bind, table_name):
            op.drop_index(index_name, table_name=table_name)

        if "visitor_id" in _columns(bind, table_name):
            with op.batch_alter_table(table_name) as batch:
                batch.drop_column("visitor_id")
