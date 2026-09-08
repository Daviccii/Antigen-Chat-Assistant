"""Attachment model — file uploads attached to conversations/messages.

Kept in its own module (rather than added to models.py) so the existing
User/Conversation/Message/Memory/Project models don't need touching.
SQLAlchemy only needs this class imported somewhere before init_db() runs
(Base.metadata.create_all) for the table to get created — see the import
added in main.py.

Phase C1 (foundation): schema + upload/storage only. `status` starts and
stays at UPLOADED for now; `extracted_text`/`embedding` are populated by
the Phase C2+ extraction pipeline, not by this file.
"""
import datetime
import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, BigInteger, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .db import Base


class AttachmentType(str, enum.Enum):
    IMAGE = "IMAGE"
    PDF = "PDF"
    DOCX = "DOCX"
    SPREADSHEET = "SPREADSHEET"  # xlsx, csv
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    CODE = "CODE"
    OTHER = "OTHER"


class AttachmentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"        # stored on disk, not yet processed
    PROCESSING = "PROCESSING"    # extraction pipeline running (Phase C2+)
    PROCESSED = "PROCESSED"      # extracted_text/embedding populated
    FAILED = "FAILED"            # extraction failed; file still on disk


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)

    # Original vs. on-disk identity. `filename` is user-facing / display
    # only — never used to build a filesystem path (see attachment_security.py).
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=False)  # relative to UPLOAD_DIR
    checksum_sha256 = Column(String(64), nullable=False, index=True)

    mime_type = Column(String(128), nullable=False)
    file_type = Column(SQLEnum(AttachmentType), nullable=False, index=True)
    size_bytes = Column(BigInteger, nullable=False)

    status = Column(SQLEnum(AttachmentStatus), default=AttachmentStatus.UPLOADED, nullable=False, index=True)

    # Populated by the Phase C2+ extraction pipeline.
    extracted_text = Column(Text, nullable=True)
    extracted_metadata = Column(Text, nullable=True)  # JSON string: page count, dimensions, duration, etc.
    processing_error = Column(Text, nullable=True)

    # 768 dims to match nomic-embed-text, same convention as Memory.embedding.
    embedding = Column(Vector(768), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    user = relationship("User")
    conversation = relationship("Conversation")
    message = relationship("Message")


Index("ix_attachments_user_id", Attachment.user_id)
Index("ix_attachments_conversation_id", Attachment.conversation_id)
Index("ix_attachments_status", Attachment.status)
Index("ix_attachments_checksum", Attachment.checksum_sha256)