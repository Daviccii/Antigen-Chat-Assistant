"""Security Gateway data models: per-user kill switch settings, allowed
file-system areas, and the audit log every gated operation writes to.

Phase D1 (foundation) - these tables back security_gateway.py. No new
Antigen capabilities (file ops, app control, etc.) are added yet; this
is just the checkpoint they'll all have to pass through.
"""
import datetime
import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship

from .db import Base


class TrustLevel(str, enum.Enum):
    """How much a file/input is trusted before Antigen acts on it.
    Mirrors the design doc's TRUSTED / UNKNOWN / UNTRUSTED / MALICIOUS_SUSPECTED
    classification. User uploads (Attachment rows) default to UNTRUSTED -
    readable/analyzable, never auto-executable.
    """
    TRUSTED = "TRUSTED"
    UNKNOWN = "UNKNOWN"
    UNTRUSTED = "UNTRUSTED"
    MALICIOUS_SUSPECTED = "MALICIOUS_SUSPECTED"


class GatewayDecision(str, enum.Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


class SecuritySettings(Base):
    """One row per user. Holds the kill switch (global + per-category)
    and the list of filesystem areas Antigen is allowed to touch at all.

    Locked-down by default: every switch defaults to OFF and
    allowed_areas starts empty, matching "broad capability, narrow
    authority" - a fresh install can't touch the filesystem or launch
    anything until the user explicitly turns categories on and adds areas.
    """
    __tablename__ = "security_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Master switch. When False, every gated operation is blocked
    # regardless of category switches below.
    computer_access_enabled = Column(Boolean, default=False, nullable=False)

    # Per-category switches, checked only when computer_access_enabled is True.
    file_read_enabled = Column(Boolean, default=False, nullable=False)
    file_modification_enabled = Column(Boolean, default=False, nullable=False)
    application_control_enabled = Column(Boolean, default=False, nullable=False)
    system_control_enabled = Column(Boolean, default=False, nullable=False)
    admin_operations_enabled = Column(Boolean, default=False, nullable=False)
    # Market data reads, indicator calculations, backtesting, and price
    # alerts — no real money ever moves regardless of this switch; it
    # just gates whether Antigen can fetch external market data at all.
    trading_enabled = Column(Boolean, default=False, nullable=False)
    # Dependency vuln scanning, static code review, local port visibility
    # — all read-only, never touches another host.
    cybersecurity_enabled = Column(Boolean, default=False, nullable=False)

    # JSON-encoded list of absolute paths Antigen may operate within.
    # Empty by default - nothing is allowed until the user adds areas.
    allowed_areas = Column(Text, default="[]", nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")


class AuditLogEntry(Base):
    """Every operation the Security Gateway evaluates gets a row here,
    whether it was allowed, blocked, or left pending confirmation -
    this is the record referenced in section 9 of the design doc.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    tool_name = Column(String(128), nullable=False, index=True)
    domain = Column(String(64), nullable=True, index=True)
    permission_level = Column(String(20), nullable=False)  # PermissionLevel value at time of the check

    decision = Column(SQLEnum(GatewayDecision), nullable=False, index=True)
    reason = Column(Text, nullable=True)  # human-readable explanation of the decision

    # Free-text summary of what was requested - e.g. the target path for a
    # file op. Deliberately not the full input payload: keeps the log
    # readable and avoids parking large blobs (like file contents) here.
    input_summary = Column(String(512), nullable=True)
    target_path = Column(String(512), nullable=True)

    # Outcome, filled in after execution (None while still pending/blocked
    # before ever running).
    execution_status = Column(String(20), nullable=True)  # SUCCESS, FAILED
    execution_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    user = relationship("User")


Index("ix_audit_log_user_created", AuditLogEntry.user_id, AuditLogEntry.created_at)