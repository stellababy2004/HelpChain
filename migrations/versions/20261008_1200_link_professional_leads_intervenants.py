"""Link professional leads to converted intervenants.

Revision ID: 20261008_1200
Revises: 20261001_1000
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261008_1200"
down_revision = "20261001_1000"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        columns = inspect(bind).get_columns(table_name)
    except Exception:
        return False
    return any(column.get("name") == column_name for column in columns)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspect(bind).get_indexes(table_name)
    except Exception:
        return False
    return any(index.get("name") == index_name for index in indexes)


def _has_foreign_key(bind, table_name: str, constrained_columns: list[str]) -> bool:
    try:
        foreign_keys = inspect(bind).get_foreign_keys(table_name)
    except Exception:
        return False
    expected = tuple(constrained_columns)
    for foreign_key in foreign_keys:
        if tuple(foreign_key.get("constrained_columns") or ()) == expected:
            return True
    return False


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        with op.batch_alter_table("professional_leads") as batch_op:
            batch_op.add_column(sa.Column("intervenant_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_professional_leads_intervenant_id_intervenants",
                "intervenants",
                ["intervenant_id"],
                ["id"],
            )
            batch_op.create_index(
                "ix_professional_leads_intervenant_id",
                ["intervenant_id"],
                unique=True,
            )
        return

    if not _has_table(bind, "professional_leads") or not _has_table(bind, "intervenants"):
        return

    with op.batch_alter_table("professional_leads") as batch_op:
        if not _has_column(bind, "professional_leads", "intervenant_id"):
            batch_op.add_column(sa.Column("intervenant_id", sa.Integer(), nullable=True))
        if not _has_foreign_key(bind, "professional_leads", ["intervenant_id"]):
            batch_op.create_foreign_key(
                "fk_professional_leads_intervenant_id_intervenants",
                "intervenants",
                ["intervenant_id"],
                ["id"],
            )

    if not _has_index(bind, "professional_leads", "ix_professional_leads_intervenant_id"):
        op.create_index(
            "ix_professional_leads_intervenant_id",
            "professional_leads",
            ["intervenant_id"],
            unique=True,
        )


def downgrade():
    # Data-safe downgrade: keep CRM-to-operational links once populated.
    pass
