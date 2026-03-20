"""add cases, case_events and case_participants tables

Revision ID: ab12cd34ef56
Revises: 6e8a1b4c9d20, 9f1d4d7d2e1a
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa


revision = "ab12cd34ef56"
down_revision = ("6e8a1b4c9d20", "9f1d4d7d2e1a")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "cases" not in tables:
        op.create_table(
            "cases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("structure_id", sa.Integer(), nullable=True),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("assigned_professional_lead_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
            sa.Column("risk_score", sa.Integer(), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["request_id"], ["requests.id"], name="fk_cases_request_id"),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"], name="fk_cases_structure_id"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["admin_users.id"], name="fk_cases_owner_user_id"),
            sa.ForeignKeyConstraint(
                ["assigned_professional_lead_id"],
                ["professional_leads.id"],
                name="fk_cases_assigned_professional_lead_id",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("request_id", name="uq_cases_request_id"),
        )

    inspector = sa.inspect(bind)
    case_indexes = {idx["name"] for idx in inspector.get_indexes("cases")}
    if "ix_cases_status" not in case_indexes:
        op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    if "ix_cases_priority" not in case_indexes:
        op.create_index("ix_cases_priority", "cases", ["priority"], unique=False)
    if "ix_cases_last_activity_at" not in case_indexes:
        op.create_index("ix_cases_last_activity_at", "cases", ["last_activity_at"], unique=False)
    if "ix_cases_owner_user_id" not in case_indexes:
        op.create_index("ix_cases_owner_user_id", "cases", ["owner_user_id"], unique=False)
    if "ix_cases_assigned_professional_lead_id" not in case_indexes:
        op.create_index(
            "ix_cases_assigned_professional_lead_id",
            "cases",
            ["assigned_professional_lead_id"],
            unique=False,
        )

    if "case_events" not in tables:
        op.create_table(
            "case_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(length=20), nullable=False, server_default="internal"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_case_events_case_id"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admin_users.id"], name="fk_case_events_actor_user_id"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    case_event_indexes = {idx["name"] for idx in inspector.get_indexes("case_events")}
    if "ix_case_events_case_id" not in case_event_indexes:
        op.create_index("ix_case_events_case_id", "case_events", ["case_id"], unique=False)
    if "ix_case_events_event_type" not in case_event_indexes:
        op.create_index("ix_case_events_event_type", "case_events", ["event_type"], unique=False)
    if "ix_case_events_visibility" not in case_event_indexes:
        op.create_index("ix_case_events_visibility", "case_events", ["visibility"], unique=False)
    if "ix_case_events_created_at" not in case_event_indexes:
        op.create_index("ix_case_events_created_at", "case_events", ["created_at"], unique=False)

    if "case_participants" not in tables:
        op.create_table(
            "case_participants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("participant_type", sa.String(length=40), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("professional_lead_id", sa.Integer(), nullable=True),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            sa.Column("role", sa.String(length=40), nullable=False, server_default="contributor"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_case_participants_case_id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_case_participants_user_id"),
            sa.ForeignKeyConstraint(
                ["professional_lead_id"],
                ["professional_leads.id"],
                name="fk_case_participants_professional_lead_id",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    participant_indexes = {idx["name"] for idx in inspector.get_indexes("case_participants")}
    if "ix_case_participants_case_id" not in participant_indexes:
        op.create_index("ix_case_participants_case_id", "case_participants", ["case_id"], unique=False)
    if "ix_case_participants_participant_type" not in participant_indexes:
        op.create_index(
            "ix_case_participants_participant_type",
            "case_participants",
            ["participant_type"],
            unique=False,
        )
    if "ix_case_participants_role" not in participant_indexes:
        op.create_index("ix_case_participants_role", "case_participants", ["role"], unique=False)


def downgrade() -> None:
    pass
