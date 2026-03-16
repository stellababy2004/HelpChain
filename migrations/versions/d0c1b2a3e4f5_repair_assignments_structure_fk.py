"""repair assignments.structure_id foreign key on SQLite

Revision ID: d0c1b2a3e4f5
Revises: c0ffee1234ab
Create Date: 2026-03-15 21:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d0c1b2a3e4f5"
down_revision = "c0ffee1234ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "assignments" not in tables or "structures" not in tables or "requests" not in tables:
        return
    # SQLite needs a table rebuild to add a foreign key constraint.
    with op.batch_alter_table("assignments", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_assignments_structure_id",
            "structures",
            ["structure_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "assignments" not in set(insp.get_table_names()):
        return
    with op.batch_alter_table("assignments", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_assignments_structure_id",
            type_="foreignkey",
        )
