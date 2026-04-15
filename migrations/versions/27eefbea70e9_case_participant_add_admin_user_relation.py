"""case_participant: add admin_user relation

Revision ID: 27eefbea70e9
Revises: c91e21741d5c
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "27eefbea70e9"
down_revision = "c91e21741d5c"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _has_fk(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    fks = inspector.get_foreign_keys(table_name)
    return any((fk.get("name") == fk_name) for fk in fks)


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("case_participants") as batch_op:
            if not _has_column("case_participants", "admin_user_id"):
                batch_op.add_column(
                    sa.Column("admin_user_id", sa.Integer(), nullable=True)
                )

            if not _has_fk("case_participants", "fk_case_participants_admin_user_id"):
                batch_op.create_foreign_key(
                    "fk_case_participants_admin_user_id",
                    "admin_users",
                    ["admin_user_id"],
                    ["id"],
                )
    else:
        if not _has_column("case_participants", "admin_user_id"):
            op.add_column(
                "case_participants",
                sa.Column("admin_user_id", sa.Integer(), nullable=True),
            )

        if not _has_fk("case_participants", "fk_case_participants_admin_user_id"):
            op.create_foreign_key(
                "fk_case_participants_admin_user_id",
                "case_participants",
                "admin_users",
                ["admin_user_id"],
                ["id"],
            )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("case_participants") as batch_op:
            if _has_fk("case_participants", "fk_case_participants_admin_user_id"):
                batch_op.drop_constraint(
                    "fk_case_participants_admin_user_id",
                    type_="foreignkey",
                )

            if _has_column("case_participants", "admin_user_id"):
                batch_op.drop_column("admin_user_id")
    else:
        if _has_fk("case_participants", "fk_case_participants_admin_user_id"):
            op.drop_constraint(
                "fk_case_participants_admin_user_id",
                "case_participants",
                type_="foreignkey",
            )

        if _has_column("case_participants", "admin_user_id"):
            op.drop_column("case_participants", "admin_user_id")