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
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("requests")}

    if "structure_id" not in cols:
        op.add_column("requests", sa.Column("structure_id", sa.Integer(), nullable=True))

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

    if dialect == "sqlite":
        # SQLite needs batch mode for FK + NOT NULL alteration
        with op.batch_alter_table("requests", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                fk_name,
                "structures",
                ["structure_id"],
                ["id"],
            )
            batch_op.alter_column("structure_id", existing_type=sa.Integer(), nullable=False)
    else:
        if fk_name not in _fk_names(insp, "requests"):
            op.create_foreign_key(
                fk_name,
                "requests",
                "structures",
                ["structure_id"],
                ["id"],
            )
        op.alter_column("requests", "structure_id", existing_type=sa.Integer(), nullable=False)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("requests")}
    if "structure_id" not in cols:
        return

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

