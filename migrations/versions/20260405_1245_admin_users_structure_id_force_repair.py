"""admin users structure id force repair

Revision ID: 20260405_1245
Revises: 20260405_1215
Create Date: 2026-04-05 12:45:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260405_1245"
down_revision = "20260405_1215"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        insp = inspect(bind)
        cols = insp.get_columns(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(c.get("name") == column_name for c in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        insp = inspect(bind)
        indexes = insp.get_indexes(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _has_foreign_key(bind, table_name: str, constrained_columns: list[str]) -> bool:
    try:
        insp = inspect(bind)
        foreign_keys = insp.get_foreign_keys(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    expected = tuple(constrained_columns)
    for fk in foreign_keys:
        cols = tuple(fk.get("constrained_columns") or ())
        if cols == expected:
            return True
    return False


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        with op.batch_alter_table("admin_users") as batch_op:
            batch_op.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        op.create_index(
            "ix_admin_users_structure_id",
            "admin_users",
            ["structure_id"],
            unique=False,
        )
        return

    if not _has_table(bind, "admin_users"):
        return

    with op.batch_alter_table("admin_users") as batch_op:
        if not _has_column(bind, "admin_users", "structure_id"):
            batch_op.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))

    # Re-inspect after possible column creation so partially drifted DBs
    # can still receive FK/index in the same migration run.
    if (
        _has_table(bind, "structures")
        and _has_column(bind, "admin_users", "structure_id")
        and not _has_foreign_key(bind, "admin_users", ["structure_id"])
    ):
        with op.batch_alter_table("admin_users") as batch_op:
            batch_op.create_foreign_key(
                "fk_admin_users_structure_id_structures",
                "structures",
                ["structure_id"],
                ["id"],
            )

    if (
        _has_column(bind, "admin_users", "structure_id")
        and not _has_index(bind, "admin_users", "ix_admin_users_structure_id")
    ):
        op.create_index(
            "ix_admin_users_structure_id",
            "admin_users",
            ["structure_id"],
            unique=False,
        )


def downgrade():
    # Data-safe downgrade: keep the repaired column/index/fk once created.
    pass
