"""add structure_id to assignments

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-15 10:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "assignments" not in tables:
        return
    existing_cols = {c["name"] for c in insp.get_columns("assignments")}
    # If referenced tables are missing (early in chain), avoid batch FK reflection.
    if "requests" not in tables or "structures" not in tables:
        if "structure_id" not in existing_cols:
            op.add_column(
                "assignments",
                sa.Column("structure_id", sa.Integer(), nullable=True),
            )
        op.create_index(
            "ix_assignments_structure_id",
            "assignments",
            ["structure_id"],
        )
        return
    with op.batch_alter_table("assignments") as batch_op:
        if "structure_id" not in existing_cols:
            batch_op.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_assignments_structure_id", ["structure_id"])
        batch_op.create_foreign_key(
            "fk_assignments_structure_id",
            "structures",
            ["structure_id"],
            ["id"],
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "assignments" not in insp.get_table_names():
        return
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint(
            "fk_assignments_structure_id", type_="foreignkey"
        )
        batch_op.drop_index("ix_assignments_structure_id")
        batch_op.drop_column("structure_id")
