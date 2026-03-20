from alembic import op
import sqlalchemy as sa

revision = "4c2f9d1a6b7e"
down_revision = "d0c1b2a3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "structures" not in set(inspector.get_table_names()):
        return

    columns = {col["name"] for col in inspector.get_columns("structures")}

    if "status" not in columns:
        op.add_column(
            "structures",
            sa.Column("status", sa.String(length=16), nullable=True),
        )
        op.execute(
            "UPDATE structures SET status = 'pending' WHERE status IS NULL"
        )

    index_names = {
        idx["name"] for idx in sa.inspect(bind).get_indexes("structures")
    }

    if "ix_structures_status" not in index_names:
        op.create_index(
            "ix_structures_status",
            "structures",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    pass
