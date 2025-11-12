"""Initial migration for PostgreSQL deployment

Revision ID: 001_initial
Revises:
Create Date: 2025-10-17 11:15:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types for PostgreSQL. Guard these so running migrations
    # against SQLite (local dev/tests) doesn't attempt to execute
    # Postgres-only DDL (which would raise sqlite3.OperationalError).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Use a DO block with IF NOT EXISTS checks so repeated runs (or
        # leftover types in a shared/test DB) do not cause DuplicateObject
        # errors. This mirrors safeguards added in later migrations and the
        # CI pre-clean step.
        op.execute(
            """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roleenum') THEN
        CREATE TYPE roleenum AS ENUM ('user', 'volunteer', 'moderator', 'admin', 'superadmin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'permissionenum') THEN
        CREATE TYPE permissionenum AS ENUM ('view_profile', 'edit_profile', 'view_volunteers', 'manage_volunteers', 'view_requests', 'manage_requests', 'use_video_chat', 'moderate_content', 'view_analytics', 'manage_categories', 'admin_access', 'manage_users', 'manage_roles', 'system_settings', 'view_audit_logs', 'super_admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'priorityenum') THEN
        CREATE TYPE priorityenum AS ENUM ('low', 'normal', 'urgent');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtypeenum') THEN
        CREATE TYPE notificationtypeenum AS ENUM ('system', 'request', 'task', 'message', 'achievement', 'reminder', 'alert');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationchannelenum') THEN
        CREATE TYPE notificationchannelenum AS ENUM ('email', 'app', 'push');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationstatusenum') THEN
        CREATE TYPE notificationstatusenum AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed', 'cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'useractivitytypeenum') THEN
        CREATE TYPE useractivitytypeenum AS ENUM (
            'page_view','page_exit','scroll','time_spent','button_click','form_submit','form_start','link_click','search_query','help_request_created','help_request_viewed','help_request_updated','task_viewed','task_accepted','task_completed','volunteer_profile_viewed','chat_message_sent','chat_room_joined','video_chat_started','login','logout','password_reset','achievement_unlocked','points_earned','level_up','error_occurred','page_not_found','form_validation_error','registration_completed','help_request_assigned','task_assigned'
        );
    END IF;
END
$$;
""",
        )
    else:
        # SQLite/local dev: skip native enum creation
        pass

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "user",
                "volunteer",
                "moderator",
                "admin",
                "superadmin",
                name="roleenum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("twofa_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_users_role", "users", ["role"], unique=False)

    # Create admin_users table
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(length=128), nullable=True),
        sa.Column("twofa_secret", sa.String(length=32), nullable=True),
        sa.Column("twofa_enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create permissions table
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create user_roles table
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create role_permissions table
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create volunteers table
    op.create_table(
        "volunteers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("skills", sa.String(length=500), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("experience", sa.Integer(), nullable=False),
        sa.Column("total_tasks_completed", sa.Integer(), nullable=False),
        sa.Column("total_hours_volunteered", sa.Float(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("achievements", sa.JSON(), nullable=False),
        sa.Column("badges", sa.JSON(), nullable=False),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("last_activity", sa.DateTime(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_volunteers_location", "volunteers", ["location"], unique=False)

    # Create achievements table
    op.create_table(
        "achievements",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("icon", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("points_reward", sa.Integer(), nullable=False),
        sa.Column("requirement_type", sa.String(length=50), nullable=False),
        sa.Column("requirement_value", sa.Integer(), nullable=False),
        sa.Column("rarity", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create help_requests table
    op.create_table(
        "help_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "normal", "urgent", name="priorityenum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_help_requests_status", "help_requests", ["status"], unique=False
    )

    # Create chat_rooms table
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create chat_participants table
    op.create_table(
        "chat_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("volunteer_id", sa.Integer(), nullable=True),
        sa.Column("participant_type", sa.String(length=20), nullable=False),
        sa.Column("participant_name", sa.String(length=100), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["chat_rooms.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["volunteer_id"],
            ["volunteers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("sender_type", sa.String(length=20), nullable=False),
        sa.Column("sender_name", sa.String(length=100), nullable=False),
        sa.Column("message_type", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reply_to_id"],
            ["chat_messages.id"],
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["chat_rooms.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "notification_type",
            postgresql.ENUM(
                "system",
                "request",
                "task",
                "message",
                "achievement",
                "reminder",
                "alert",
                name="notificationtypeenum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("recipient_type", sa.String(length=20), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column(
            "email_status",
            postgresql.ENUM(
                "pending",
                "sent",
                "delivered",
                "read",
                "failed",
                "cancelled",
                name="notificationstatusenum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "app_status",
            postgresql.ENUM(
                "pending",
                "sent",
                "delivered",
                "read",
                "failed",
                "cancelled",
                name="notificationstatusenum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "push_status",
            postgresql.ENUM(
                "pending",
                "sent",
                "delivered",
                "read",
                "failed",
                "cancelled",
                name="notificationstatusenum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "normal", "urgent", name="priorityenum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("related_type", sa.String(length=50), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("action_url", sa.String(length=500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_notifications_recipient",
        "notifications",
        ["recipient_id", "recipient_type"],
        unique=False,
    )
    op.create_index(
        "idx_notifications_type", "notifications", ["notification_type"], unique=False
    )
    op.create_index(
        "idx_notifications_status",
        "notifications",
        ["email_status", "app_status", "push_status"],
        unique=False,
    )
    op.create_index(
        "idx_notifications_created", "notifications", ["created_at"], unique=False
    )

    # Create user_activities table
    op.create_table(
        "user_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_type", sa.String(length=20), nullable=True),
        sa.Column(
            "activity_type",
            postgresql.ENUM(
                "page_view",
                "page_exit",
                "scroll",
                "time_spent",
                "button_click",
                "form_submit",
                "form_start",
                "link_click",
                "search_query",
                "help_request_created",
                "help_request_viewed",
                "help_request_updated",
                "task_viewed",
                "task_accepted",
                "task_completed",
                "volunteer_profile_viewed",
                "chat_message_sent",
                "chat_room_joined",
                "video_chat_started",
                "login",
                "logout",
                "password_reset",
                "achievement_unlocked",
                "points_earned",
                "level_up",
                "error_occurred",
                "page_not_found",
                "form_validation_error",
                "registration_completed",
                "help_request_assigned",
                "task_assigned",
                name="useractivitytypeenum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("activity_description", sa.String(length=255), nullable=True),
        sa.Column("activity_data", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=True),
        sa.Column("browser", sa.String(length=100), nullable=True),
        sa.Column("os", sa.String(length=100), nullable=True),
        sa.Column("screen_resolution", sa.String(length=20), nullable=True),
        sa.Column("page_url", sa.String(length=500), nullable=True),
        sa.Column("page_title", sa.String(length=255), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("referrer_domain", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("time_on_page", sa.Integer(), nullable=True),
        sa.Column("related_type", sa.String(length=50), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("ai_processed", sa.Boolean(), nullable=True),
        sa.Column("ai_insights", sa.JSON(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("engagement_score", sa.Float(), nullable=True),
        sa.Column("experiment_id", sa.String(length=100), nullable=True),
        sa.Column("experiment_variant", sa.String(length=100), nullable=True),
        sa.Column("activity_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_activities_user_session",
        "user_activities",
        ["user_id", "session_id"],
        unique=False,
    )
    op.create_index(
        "idx_user_activities_type_timestamp",
        "user_activities",
        ["activity_type", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_user_activities_page", "user_activities", ["page_url"], unique=False
    )
    op.create_index(
        "idx_user_activities_related",
        "user_activities",
        ["related_type", "related_id"],
        unique=False,
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table("user_activities")
    op.drop_table("notifications")
    op.drop_table("chat_messages")
    op.drop_table("chat_participants")
    op.drop_table("chat_rooms")
    op.drop_table("help_requests")
    op.drop_table("audit_logs")
    op.drop_table("achievements")
    op.drop_table("volunteers")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("admin_users")
    op.drop_table("users")

    # Drop enum types
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS useractivitytypeenum")
        op.execute("DROP TYPE IF EXISTS notificationstatusenum")
        op.execute("DROP TYPE IF EXISTS notificationchannelenum")
        op.execute("DROP TYPE IF EXISTS notificationtypeenum")
        op.execute("DROP TYPE IF EXISTS priorityenum")
        op.execute("DROP TYPE IF EXISTS permissionenum")
        op.execute("DROP TYPE IF EXISTS roleenum")
    else:
        # Nothing to drop on SQLite
        pass
