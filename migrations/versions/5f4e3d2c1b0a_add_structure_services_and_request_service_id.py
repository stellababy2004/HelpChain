"""add structure services and request service_id

Revision ID: 5f4e3d2c1b0a
Revises: 1a2b3c4d5e6f
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa


revision = "5f4e3d2c1b0a"
down_revision = "1a2b3c4d5e6f"
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
    return any((idx.get("name") or "") == index_name for idx in insp.get_indexes(table_name))


def fk_exists(bind, table_name, fk_name):
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    for fk in insp.get_foreign_keys(table_name):
        if (fk.get("name") or "") == fk_name:
            return True
    return False


def upgrade():
    bind = op.get_bind()

    if table_exists(bind, "structures") and not table_exists(bind, "structure_services"):
        op.create_table(
            "structure_services",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("structure_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.UniqueConstraint(
                "structure_id", "code", name="uq_structure_services_structure_code"
            ),
            sa.UniqueConstraint(
                "structure_id", "name", name="uq_structure_services_structure_name"
            ),
        )

    if table_exists(bind, "structure_services") and not index_exists(
        bind, "structure_services", "ix_structure_services_structure_active"
    ):
        op.create_index(
            "ix_structure_services_structure_active",
            "structure_services",
            ["structure_id", "is_active"],
            unique=False,
        )

    if not table_exists(bind, "requests"):
        return

    if not column_exists(bind, "requests", "service_id"):
        op.add_column("requests", sa.Column("service_id", sa.Integer(), nullable=True))

    if not index_exists(bind, "requests", "ix_requests_service_id"):
        op.create_index("ix_requests_service_id", "requests", ["service_id"], unique=False)

    if (
        bind.dialect.name != "sqlite"
        and table_exists(bind, "structure_services")
        and not fk_exists(bind, "requests", "fk_requests_service_id")
    ):
        op.create_foreign_key(
            "fk_requests_service_id",
            "requests",
            "structure_services",
            ["service_id"],
            ["id"],
        )


def downgrade():
    bind = op.get_bind()

    if table_exists(bind, "requests") and column_exists(bind, "requests", "service_id"):
        if bind.dialect.name != "sqlite" and fk_exists(bind, "requests", "fk_requests_service_id"):
            op.drop_constraint("fk_requests_service_id", "requests", type_="foreignkey")

        if index_exists(bind, "requests", "ix_requests_service_id"):
            op.drop_index("ix_requests_service_id", table_name="requests")

        op.drop_column("requests", "service_id")

    if table_exists(bind, "structure_services"):
        if index_exists(bind, "structure_services", "ix_structure_services_structure_active"):
            op.drop_index(
                "ix_structure_services_structure_active", table_name="structure_services"
            )
        op.drop_table("structure_services")
