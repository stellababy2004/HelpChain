"""add structure_id to requests

Revision ID: d8a7c6b5e4f3
Revises: c4f3d2a1b0e9
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa


revision = "d8a7c6b5e4f3"
down_revision = "c4f3d2a1b0e9"
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


def _column_nullable(bind, table_name: str, column_name: str):
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return None
    for col in insp.get_columns(table_name):
        if col.get("name") == column_name:
            return col.get("nullable")
    return None


def _fk_names(insp, table_name: str) -> set[str]:
    out = set()
    try:
        for fk in insp.get_foreign_keys(table_name):
            name = fk.get("name")
            if name:
                out.add(name)
    except Exception:
        pass
    return out


def upgrade():
    bind = op.get_bind()
    if not table_exists(bind, "requests"):
        return

    if not column_exists(bind, "requests", "structure_id"):
        op.add_column("requests", sa.Column("structure_id", sa.Integer(), nullable=True))

    if not table_exists(bind, "structures"):
        return

    insp = sa.inspect(bind)

    # Backfill to default structure row (expected id=1; fallback by slug)
    bind.execute(
        sa.text(
            """
            UPDATE requests
            SET structure_id = COALESCE(
                (SELECT id FROM structures WHERE slug = 'default' LIMIT 1),
                1
            )
            WHERE structure_id IS NULL
            """
        )
    )

    dialect = bind.dialect.name
    fk_name = "fk_requests_structure_id"
    fk_exists = fk_name in _fk_names(insp, "requests")
    nullable = _column_nullable(bind, "requests", "structure_id")

    if dialect == "sqlite":
        # SQLite needs batch mode for FK + NOT NULL alteration
        with op.batch_alter_table("requests", recreate="always") as batch_op:
            if not fk_exists:
                batch_op.create_foreign_key(
                    fk_name,
                    "structures",
                    ["structure_id"],
                    ["id"],
                )
            if nullable is not False:
                batch_op.alter_column(
                    "structure_id", existing_type=sa.Integer(), nullable=False
                )
    else:
        if not fk_exists:
            op.create_foreign_key(
                fk_name,
                "requests",
                "structures",
                ["structure_id"],
                ["id"],
            )
        if nullable is not False:
            op.alter_column(
                "requests", "structure_id", existing_type=sa.Integer(), nullable=False
            )


def downgrade():
    bind = op.get_bind()
    if not table_exists(bind, "requests"):
        return
    if not column_exists(bind, "requests", "structure_id"):
        return

    insp = sa.inspect(bind)

    fk_name = "fk_requests_structure_id"
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("requests", recreate="always") as batch_op:
            try:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            except Exception:
                pass
            batch_op.drop_column("structure_id")
    else:
        if fk_name in _fk_names(insp, "requests"):
            op.drop_constraint(fk_name, "requests", type_="foreignkey")
        op.drop_column("requests", "structure_id")

