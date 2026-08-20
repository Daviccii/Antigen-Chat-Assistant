import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .db import Base
import enum


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    USER = "USER"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    display_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    user = relationship("User", back_populates="conversations")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")


# Indexes to support common queries: by conversation, created_at, and text searches
Index("ix_messages_conversation_id", Message.conversation_id)
Index("ix_messages_created_at", Message.created_at)
Index("ix_conversations_created_at", Conversation.created_at)
Index("ix_conversations_user_id", Conversation.user_id)


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(64), nullable=False, index=False)
    key = Column(String(256), nullable=True, index=False)
    content = Column(Text, nullable=False)
    source = Column(String(128), nullable=True)
    tags = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # 768 dims matches nomic-embed-text (the local Ollama embedding model
    # used in services.py). If you switch embedding models, this dimension
    # must match, and existing embeddings need regenerating — they aren't
    # portable across models with different output sizes.
    embedding = Column(Vector(768), nullable=True)
    user = relationship("User", back_populates="memories")


# Indexes for memories
Index("ix_memories_type", Memory.type)
Index("ix_memories_key", Memory.key)
Index("ix_memories_created_at", Memory.created_at)
Index("ix_memories_user_id", Memory.user_id)