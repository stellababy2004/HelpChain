"""add structures table

Revision ID: c4f3d2a1b0e9
Revises: b2d5c3f1a9e0
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f3d2a1b0e9"
down_revision = "b2d5c3f1a9e0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "structures" not in tables:
        op.create_table(
            "structures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_unique_constraint("uq_structures_slug", "structures", ["slug"])

    # SQLite-safe fixed timestamp
    row = bind.execute(sa.text("SELECT id FROM structures WHERE slug = 'default' LIMIT 1")).fetchone()
    if not row:
        op.execute(
            "INSERT INTO structures (name, slug, created_at) "
            "VALUES ('Default', 'default', '2026-01-01 00:00:00')"
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "structures" in tables:
        op.drop_table("structures")

