"""add operational fields to intervenants

Revision ID: 20260514_1500
Revises: 20260506_2100
Create Date: 2026-05-14 15:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260514_1500"
down_revision = "20260506_2100"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    insp = inspect(bind)
    try:
        return table_name in insp.get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    insp = inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "intervenants"):
        return

    with op.batch_alter_table("intervenants") as batch_op:
        if not _has_column(bind, "intervenants", "internal_notes"):
            batch_op.add_column(sa.Column("internal_notes", sa.Text(), nullable=True))
        if not _has_column(bind, "intervenants", "availability"):
            batch_op.add_column(sa.Column("availability", sa.String(length=32), nullable=True))
        if not _has_column(bind, "intervenants", "competencies_json"):
            batch_op.add_column(sa.Column("competencies_json", sa.Text(), nullable=True))
        if not _has_column(bind, "intervenants", "coverage_zones"):
            batch_op.add_column(sa.Column("coverage_zones", sa.Text(), nullable=True))
        if not _has_column(bind, "intervenants", "coverage_communes"):
            batch_op.add_column(sa.Column("coverage_communes", sa.Text(), nullable=True))
        if not _has_column(bind, "intervenants", "radius_km"):
            batch_op.add_column(sa.Column("radius_km", sa.Float(), nullable=True))
        if not _has_column(bind, "intervenants", "updated_at"):
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    if not _has_table(bind, "intervenant_activities"):
        op.create_table(
            "intervenant_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("intervenant_id", sa.Integer(), nullable=False),
            sa.Column("structure_id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=True),
            sa.Column("actor_admin_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("meta_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["intervenant_id"], ["intervenants.id"]),
            sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_intervenant_activities_actor_admin_id",
            "intervenant_activities",
            ["actor_admin_id"],
        )
        op.create_index(
            "ix_intervenant_activities_created_at",
            "intervenant_activities",
            ["created_at"],
        )
        op.create_index(
            "ix_intervenant_activities_event_type",
            "intervenant_activities",
            ["event_type"],
        )
        op.create_index(
            "ix_intervenant_activities_intervenant_id",
            "intervenant_activities",
            ["intervenant_id"],
        )
        op.create_index(
            "ix_intervenant_activities_request_id",
            "intervenant_activities",
            ["request_id"],
        )
        op.create_index(
            "ix_intervenant_activities_structure_id",
            "intervenant_activities",
            ["structure_id"],
        )


def downgrade():
    # Data-safe downgrade: keep local operational notes and availability once populated.
    pass
