"""add volunteer_id to request_activities

Revision ID: d3f1b6e4c2a9
Revises: a91d5f3c2b7e
Create Date: 2026-02-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d3f1b6e4c2a9"
down_revision = "a91d5f3c2b7e"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "request_activities"
    if table_name not in inspector.get_table_names():
        return

    cols = {c.get("name") for c in inspector.get_columns(table_name)}
    if "volunteer_id" not in cols:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("volunteer_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_request_activities_volunteer_id_volunteers",
                "volunteers",
                ["volunteer_id"],
                ["id"],
            )

    indexes = {idx.get("name") for idx in inspector.get_indexes(table_name)}
    ix_name = "ix_request_activities_volunteer_id"
    if ix_name not in indexes:
        op.create_index(ix_name, table_name, ["volunteer_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "request_activities"
    if table_name not in inspector.get_table_names():
        return

    cols = {c.get("name") for c in inspector.get_columns(table_name)}
    if "volunteer_id" not in cols:
        return

    indexes = {idx.get("name") for idx in inspector.get_indexes(table_name)}
    ix_name = "ix_request_activities_volunteer_id"
    if ix_name in indexes:
        op.drop_index(ix_name, table_name=table_name)

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_constraint(
            "fk_request_activities_volunteer_id_volunteers", type_="foreignkey"
        )
        batch_op.drop_column("volunteer_id")
