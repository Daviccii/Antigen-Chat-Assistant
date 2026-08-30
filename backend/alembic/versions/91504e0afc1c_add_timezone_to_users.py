"""initial database schema

Revision ID: 91504e0afc1c
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "91504e0afc1c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Ensure pgvector is available
    try:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    except Exception:
        conn.rollback()

    # Ensure userrole enum exists
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'userrole'
            ) THEN
                CREATE TYPE userrole AS ENUM ('OWNER', 'USER');
            END IF;
        END
        $$;
    """))
    conn.commit()

    # USERS
    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(50), unique=True, nullable=False),
            sa.Column("email", sa.String(100), unique=True, nullable=True),
            sa.Column("display_name", sa.String(100), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column(
                "role",
                postgresql.ENUM(
                    "OWNER",
                    "USER",
                    name="userrole",
                    create_type=False,
                ),
                nullable=False,
                server_default="USER",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "timezone",
                sa.String(50),
                nullable=False,
                server_default="Africa/Nairobi",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("last_login", sa.DateTime(), nullable=True),
        )

        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # CONVERSATIONS
    if "conversations" not in inspector.get_table_names():
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
        )

        op.create_index("ix_conversations_id", "conversations", ["id"])
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
        op.create_index(
            "ix_conversations_created_at",
            "conversations",
            ["created_at"],
        )

    # MESSAGES
    if "messages" not in inspector.get_table_names():
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), nullable=True),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["conversations.id"],
                ondelete="CASCADE",
            ),
        )

        op.create_index("ix_messages_id", "messages", ["id"])
        op.create_index(
            "ix_messages_conversation_id",
            "messages",
            ["conversation_id"],
        )
        op.create_index(
            "ix_messages_created_at",
            "messages",
            ["created_at"],
        )

    # MEMORIES
    if "memories" not in inspector.get_table_names():
        op.create_table(
            "memories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(64), nullable=False),
            sa.Column("category", sa.String(64), nullable=True),
            sa.Column("key", sa.String(256), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source", sa.String(64), nullable=True),
            sa.Column("importance", sa.String(20), nullable=True, server_default="NORMAL"),
            sa.Column("confidence", sa.Float(), nullable=True, server_default="0.5"),
            sa.Column("status", sa.String(20), nullable=True, server_default="ACTIVE"),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("tags", sa.String(256), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
            sa.Column("last_confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("embedding", sa.Text(), nullable=True),
            sa.Column("extra_metadata", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
        )

        op.create_index("ix_memories_id", "memories", ["id"])
        op.create_index("ix_memories_user_id", "memories", ["user_id"])
        op.create_index("ix_memories_type", "memories", ["type"])
        op.create_index("ix_memories_category", "memories", ["category"])
        op.create_index("ix_memories_key", "memories", ["key"])
        op.create_index("ix_memories_created_at", "memories", ["created_at"])
        op.create_index("ix_memories_project_id", "memories", ["project_id"])
        op.create_index("ix_memories_importance", "memories", ["importance"])
        op.create_index("ix_memories_status", "memories", ["status"])
        op.create_index("ix_memories_source", "memories", ["source"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "memories" in inspector.get_table_names():
        op.drop_table("memories")

    if "messages" in inspector.get_table_names():
        op.drop_table("messages")

    if "conversations" in inspector.get_table_names():
        op.drop_table("conversations")

    if "users" in inspector.get_table_names():
        op.drop_table("users")

    conn.execute(sa.text("DROP TYPE IF EXISTS userrole"))
    conn.commit()
