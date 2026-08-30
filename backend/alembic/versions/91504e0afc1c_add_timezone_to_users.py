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
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    user_role = sa.Enum("OWNER", "USER", name="userrole")
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_conversations_id", "conversations", ["id"], unique=False)
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_messages_id", "messages", ["id"], unique=False)
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)

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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_memories_id", "memories", ["id"], unique=False)
    op.create_index("ix_memories_user_id", "memories", ["user_id"], unique=False)
    op.create_index("ix_memories_type", "memories", ["type"], unique=False)
    op.create_index("ix_memories_category", "memories", ["category"], unique=False)
    op.create_index("ix_memories_key", "memories", ["key"], unique=False)
    op.create_index("ix_memories_created_at", "memories", ["created_at"], unique=False)
    op.create_index("ix_memories_project_id", "memories", ["project_id"], unique=False)
    op.create_index("ix_memories_importance", "memories", ["importance"], unique=False)
    op.create_index("ix_memories_status", "memories", ["status"], unique=False)
    op.create_index("ix_memories_source", "memories", ["source"], unique=False)


def downgrade() -> None:
    op.drop_table("memories")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")

    user_role = sa.Enum("OWNER", "USER", name="userrole")
    user_role.drop(op.get_bind(), checkfirst=True)
