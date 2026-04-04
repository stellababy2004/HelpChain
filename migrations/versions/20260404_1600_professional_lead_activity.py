"""add professional lead last touch and activity log

Revision ID: 20260404_1600
Revises: 20260404_1015
Create Date: 2026-04-04 16:00:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260404_1600"
down_revision = "20260404_1015"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        insp = inspect(bind)
        cols = insp.get_columns(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(c.get("name") == column_name for c in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        insp = inspect(bind)
        indexes = insp.get_indexes(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _has_foreign_key(bind, table_name: str, constrained_columns: list[str]) -> bool:
    try:
        insp = inspect(bind)
        foreign_keys = insp.get_foreign_keys(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    expected = tuple(constrained_columns)
    for fk in foreign_keys:
        cols = tuple(fk.get("constrained_columns") or ())
        if cols == expected:
            return True
    return False


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        with op.batch_alter_table("professional_leads") as batch_op:
            batch_op.add_column(
                sa.Column("last_touched_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.add_column(
                sa.Column("last_touched_by_admin_id", sa.Integer(), nullable=True)
            )
        op.create_index(
            "ix_professional_leads_last_touched_at",
            "professional_leads",
            ["last_touched_at"],
            unique=False,
        )
        op.create_index(
            "ix_professional_leads_last_touched_by_admin_id",
            "professional_leads",
            ["last_touched_by_admin_id"],
            unique=False,
        )
        op.create_table(
            "professional_lead_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("professional_lead_id", sa.Integer(), nullable=False),
            sa.Column("admin_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["professional_lead_id"], ["professional_leads.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_professional_lead_activities_professional_lead_id",
            "professional_lead_activities",
            ["professional_lead_id"],
            unique=False,
        )
        op.create_index(
            "ix_professional_lead_activities_admin_user_id",
            "professional_lead_activities",
            ["admin_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_professional_lead_activities_action",
            "professional_lead_activities",
            ["action"],
            unique=False,
        )
        op.create_index(
            "ix_professional_lead_activities_created_at",
            "professional_lead_activities",
            ["created_at"],
            unique=False,
        )
        return

    if _has_table(bind, "professional_leads"):
        with op.batch_alter_table("professional_leads") as batch_op:
            if not _has_column(bind, "professional_leads", "last_touched_at"):
                batch_op.add_column(
                    sa.Column("last_touched_at", sa.DateTime(timezone=True), nullable=True)
                )
            if not _has_column(bind, "professional_leads", "last_touched_by_admin_id"):
                batch_op.add_column(
                    sa.Column("last_touched_by_admin_id", sa.Integer(), nullable=True)
                )
            if not _has_foreign_key(bind, "professional_leads", ["last_touched_by_admin_id"]):
                batch_op.create_foreign_key(
                    "fk_professional_leads_last_touched_by_admin_id_admin_users",
                    "admin_users",
                    ["last_touched_by_admin_id"],
                    ["id"],
                )

        if not _has_index(bind, "professional_leads", "ix_professional_leads_last_touched_at"):
            op.create_index(
                "ix_professional_leads_last_touched_at",
                "professional_leads",
                ["last_touched_at"],
                unique=False,
            )
        if not _has_index(
            bind,
            "professional_leads",
            "ix_professional_leads_last_touched_by_admin_id",
        ):
            op.create_index(
                "ix_professional_leads_last_touched_by_admin_id",
                "professional_leads",
                ["last_touched_by_admin_id"],
                unique=False,
            )

    if not _has_table(bind, "professional_lead_activities"):
        op.create_table(
            "professional_lead_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("professional_lead_id", sa.Integer(), nullable=False),
            sa.Column("admin_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["professional_lead_id"], ["professional_leads.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    for table_name, index_name, columns in (
        (
            "professional_lead_activities",
            "ix_professional_lead_activities_professional_lead_id",
            ["professional_lead_id"],
        ),
        (
            "professional_lead_activities",
            "ix_professional_lead_activities_admin_user_id",
            ["admin_user_id"],
        ),
        ("professional_lead_activities", "ix_professional_lead_activities_action", ["action"]),
        (
            "professional_lead_activities",
            "ix_professional_lead_activities_created_at",
            ["created_at"],
        ),
    ):
        if _has_table(bind, table_name) and not _has_index(bind, table_name, index_name):
            op.create_index(index_name, table_name, columns, unique=False)


def downgrade():
    # Data-safe downgrade: keep the table and columns once created.
    pass
