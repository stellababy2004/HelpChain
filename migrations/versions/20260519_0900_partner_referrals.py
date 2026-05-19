"""add partner referrals

Revision ID: 20260519_0900
Revises: 20260514_1500
Create Date: 2026-05-19 09:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260519_0900"
down_revision = "20260514_1500"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return bool(inspect(bind).has_table(table_name))
    except Exception:
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspect(bind).get_indexes(table_name)
    except Exception:
        return False
    return any(str(idx.get("name")) == index_name for idx in indexes)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if _has_table(bind, table_name) and _has_index(bind, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, "organization_connections"):
        op.create_table(
            "organization_connections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_structure_id", sa.Integer(), nullable=False),
            sa.Column("target_structure_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
            sa.Column("connection_type", sa.String(length=32), server_default="referral", nullable=False),
            sa.Column("permissions_json", sa.JSON(), nullable=True),
            sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["source_structure_id"], ["structures.id"]),
            sa.ForeignKeyConstraint(["target_structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "source_structure_id",
                "target_structure_id",
                "connection_type",
                name="uq_org_connections_source_target_type",
            ),
        )
    for index_name, columns, unique in (
        ("ix_organization_connections_source_structure_id", ["source_structure_id"], False),
        ("ix_organization_connections_target_structure_id", ["target_structure_id"], False),
        ("ix_organization_connections_status", ["status"], False),
        ("ix_organization_connections_connection_type", ["connection_type"], False),
        ("ix_organization_connections_created_by_admin_id", ["created_by_admin_id"], False),
        ("ix_organization_connections_created_at", ["created_at"], False),
        ("ix_org_connections_source_status", ["source_structure_id", "status"], False),
        ("ix_org_connections_target_status", ["target_structure_id", "status"], False),
    ):
        if not _has_index(bind, "organization_connections", index_name):
            op.create_index(index_name, "organization_connections", columns, unique=unique)

    if not _has_table(bind, "case_referrals"):
        op.create_table(
            "case_referrals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.Integer(), nullable=True),
            sa.Column("from_structure_id", sa.Integer(), nullable=False),
            sa.Column("to_structure_id", sa.Integer(), nullable=False),
            sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="sent", nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("shared_scope_json", sa.JSON(), nullable=False),
            sa.Column("accepted_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("refused_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("refusal_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["accepted_by_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["from_structure_id"], ["structures.id"]),
            sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
            sa.ForeignKeyConstraint(["to_structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns, unique in (
        ("ix_case_referrals_case_id", ["case_id"], False),
        ("ix_case_referrals_request_id", ["request_id"], False),
        ("ix_case_referrals_from_structure_id", ["from_structure_id"], False),
        ("ix_case_referrals_to_structure_id", ["to_structure_id"], False),
        ("ix_case_referrals_created_by_admin_id", ["created_by_admin_id"], False),
        ("ix_case_referrals_accepted_by_admin_id", ["accepted_by_admin_id"], False),
        ("ix_case_referrals_status", ["status"], False),
        ("ix_case_referrals_created_at", ["created_at"], False),
        ("ix_case_referrals_from_status_created", ["from_structure_id", "status", "created_at"], False),
        ("ix_case_referrals_to_status_created", ["to_structure_id", "status", "created_at"], False),
    ):
        if not _has_index(bind, "case_referrals", index_name):
            op.create_index(index_name, "case_referrals", columns, unique=unique)

    if not _has_table(bind, "referral_activities"):
        op.create_table(
            "referral_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("referral_id", sa.Integer(), nullable=False),
            sa.Column("actor_admin_id", sa.Integer(), nullable=True),
            sa.Column("actor_structure_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["actor_structure_id"], ["structures.id"]),
            sa.ForeignKeyConstraint(["referral_id"], ["case_referrals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns, unique in (
        ("ix_referral_activities_referral_id", ["referral_id"], False),
        ("ix_referral_activities_actor_admin_id", ["actor_admin_id"], False),
        ("ix_referral_activities_actor_structure_id", ["actor_structure_id"], False),
        ("ix_referral_activities_action", ["action"], False),
        ("ix_referral_activities_created_at", ["created_at"], False),
    ):
        if not _has_index(bind, "referral_activities", index_name):
            op.create_index(index_name, "referral_activities", columns, unique=unique)


def downgrade():
    bind = op.get_bind()
    for index_name in (
        "ix_referral_activities_created_at",
        "ix_referral_activities_action",
        "ix_referral_activities_actor_structure_id",
        "ix_referral_activities_actor_admin_id",
        "ix_referral_activities_referral_id",
    ):
        _drop_index_if_exists(bind, "referral_activities", index_name)
    if _has_table(bind, "referral_activities"):
        op.drop_table("referral_activities")

    for index_name in (
        "ix_case_referrals_to_status_created",
        "ix_case_referrals_from_status_created",
        "ix_case_referrals_created_at",
        "ix_case_referrals_status",
        "ix_case_referrals_accepted_by_admin_id",
        "ix_case_referrals_created_by_admin_id",
        "ix_case_referrals_to_structure_id",
        "ix_case_referrals_from_structure_id",
        "ix_case_referrals_request_id",
        "ix_case_referrals_case_id",
    ):
        _drop_index_if_exists(bind, "case_referrals", index_name)
    if _has_table(bind, "case_referrals"):
        op.drop_table("case_referrals")

    for index_name in (
        "ix_org_connections_target_status",
        "ix_org_connections_source_status",
        "ix_organization_connections_created_at",
        "ix_organization_connections_created_by_admin_id",
        "ix_organization_connections_connection_type",
        "ix_organization_connections_status",
        "ix_organization_connections_target_structure_id",
        "ix_organization_connections_source_structure_id",
    ):
        _drop_index_if_exists(bind, "organization_connections", index_name)
    if _has_table(bind, "organization_connections"):
        op.drop_table("organization_connections")
