import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, Boolean, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from .db import Base
import enum

# pgvector support - now that extension is properly installed
from pgvector.sqlalchemy import Vector
PGVECTOR_AVAILABLE = True


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
    timezone = Column(String(50), default="Africa/Nairobi", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


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


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Memory categorization
    type = Column(String(64), nullable=False, index=False)  # fact, preference, project, correction, etc.
    category = Column(String(64), nullable=True, index=True)  # user_profile, explicit, project, preference, conversational, correction
    key = Column(String(256), nullable=True, index=False)
    content = Column(Text, nullable=False)
    
    # Memory metadata
    source = Column(String(64), nullable=True)  # USER_EXPLICIT, USER_CORRECTION, CONVERSATION, SYSTEM, IMPORTED, INFERRED
    importance = Column(String(20), nullable=True, default="NORMAL")  # LOW, NORMAL, HIGH, CRITICAL
    confidence = Column(Float, nullable=True, default=0.5)  # 0.0 to 1.0
    status = Column(String(20), nullable=True, default="ACTIVE")  # ACTIVE, ARCHIVED, SUPERSEDED
    
    # Project association
    project_id = Column(Integer, nullable=True, index=True)  # Foreign key added in migration
    
    # Temporal tracking
    tags = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    last_accessed_at = Column(DateTime, nullable=True)
    last_confirmed_at = Column(DateTime, nullable=True)
    
    # Embedding for semantic search - pgvector is now properly installed
    # 768 dims matches nomic-embed-text (the local Ollama embedding model)
    embedding = Column(Vector(768), nullable=True)
    
    # Additional metadata as JSON
    extra_metadata = Column(Text, nullable=True)  # JSON string for flexible additional data
    
    user = relationship("User", back_populates="memories")


class Project(Base):
    """Project model for associating memories with specific projects."""
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="projects")
    # memories relationship will be established after migration adds foreign key