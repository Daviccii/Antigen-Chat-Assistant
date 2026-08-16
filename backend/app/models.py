import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship
from .db import Base


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


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


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(64), nullable=False, index=False)
    key = Column(String(256), nullable=True, index=False)
    content = Column(Text, nullable=False)
    source = Column(String(128), nullable=True)
    tags = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Embedding column stored as text when pgvector is unavailable so the app can still start.
    embedding = Column(Text, nullable=True)


# Indexes for memories
Index("ix_memories_type", Memory.type)
Index("ix_memories_key", Memory.key)
Index("ix_memories_created_at", Memory.created_at)
