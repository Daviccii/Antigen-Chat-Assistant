"""Security Gateway — the checkpoint every Antigen capability routes
through before it's allowed to touch the filesystem, launch an
application, or affect the system.

Nothing about *what* a capability does lives here — this module only
answers three questions: is this operation allowed right now (kill
switch + permission tier), is this path inside somewhere Antigen is
allowed to work, and — regardless of either answer — write it to the
audit log.

Phase D1 (foundation): the gateway itself, no capabilities wired to it
yet. Phase D2+ (file/app/system tools) will call check_permission() and
check_path_allowed() before doing anything real.
"""
import json
import logging
from pathlib import Path
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from .capability_system import PermissionLevel
from .security_models import SecuritySettings, AuditLogEntry, GatewayDecision, TrustLevel

logger = logging.getLogger(__name__)


# Tiers that can never be satisfied by a confirmation dialog — blocked
# outright regardless of settings, matching "RESTRICTED ... blocked by
# default" in the design doc. This is intentionally not configurable
# through SecuritySettings; loosening it needs a code change, not a toggle.
ALWAYS_BLOCKED = {PermissionLevel.RESTRICTED}

# Tiers where the operation is allowed to proceed automatically once the
# relevant category switch is on, vs. tiers that need a per-operation
# confirmation even when the category is enabled.
CONFIRMATION_POLICY = {
    PermissionLevel.READ_ONLY: False,
    PermissionLevel.SAFE_ACTION: False,
    PermissionLevel.MODIFY: True,
    PermissionLevel.DESTRUCTIVE: True,
    PermissionLevel.ADMIN: True,
}

# Defense in depth (design doc point 4/5): these are never allowed even
# if a user somehow adds them to allowed_areas — checked in addition to,
# not instead of, the allowed_areas membership check. Covers the common
# Windows/Linux/Mac sensitive locations.
DENIED_PATH_FRAGMENTS = [
    "windows", "program files", "programdata", "system32",
    "/etc", "/boot", "/sys", "/proc", "/root",
    ".ssh", ".gnupg", ".aws", ".config/gcloud",
    "security configuration", "registry",
]

# Which SecuritySettings category switch governs which tool domain +
# permission level. Checked after computer_access_enabled (the master
# switch) — a domain not listed here defaults to needing
# admin_operations_enabled, i.e. locked down until explicitly mapped.
_CATEGORY_BY_DOMAIN = {
    "file_system": {
        PermissionLevel.READ_ONLY: "file_read_enabled",
        PermissionLevel.SAFE_ACTION: "file_read_enabled",
        PermissionLevel.MODIFY: "file_modification_enabled",
        PermissionLevel.DESTRUCTIVE: "file_modification_enabled",
    },
    "applications": {
        PermissionLevel.READ_ONLY: "application_control_enabled",
        PermissionLevel.SAFE_ACTION: "application_control_enabled",
        PermissionLevel.MODIFY: "application_control_enabled",
        PermissionLevel.DESTRUCTIVE: "application_control_enabled",
    },
    "system": {
        PermissionLevel.READ_ONLY: "system_control_enabled",
        PermissionLevel.SAFE_ACTION: "system_control_enabled",
        PermissionLevel.MODIFY: "system_control_enabled",
        PermissionLevel.DESTRUCTIVE: "system_control_enabled",
        PermissionLevel.ADMIN: "admin_operations_enabled",
    },
    "finance": {
        PermissionLevel.READ_ONLY: "trading_enabled",
        PermissionLevel.SAFE_ACTION: "trading_enabled",
    },
    "software_engineering": {
        # analyze_project_structure only reads directory listings — same
        # risk tier as file_system reads, so it shares that switch rather
        # than needing its own category for one read-only tool.
        PermissionLevel.READ_ONLY: "file_read_enabled",
        PermissionLevel.SAFE_ACTION: "file_read_enabled",
    },
    "cybersecurity": {
        PermissionLevel.READ_ONLY: "cybersecurity_enabled",
        PermissionLevel.SAFE_ACTION: "cybersecurity_enabled",
    },
}


class GatewayResult:
    def __init__(self, decision: GatewayDecision, reason: str):
        self.decision = decision
        self.reason = reason

    @property
    def allowed(self) -> bool:
        return self.decision == GatewayDecision.ALLOWED

    def __repr__(self):
        return f"GatewayResult({self.decision.value}: {self.reason})"


def get_or_create_settings(db: Session, user_id: int) -> SecuritySettings:
    """Every user gets a locked-down-by-default settings row the first
    time the gateway (or the settings endpoint) touches their account.
    """
    settings = db.query(SecuritySettings).filter(SecuritySettings.user_id == user_id).first()
    if settings:
        return settings

    settings = SecuritySettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def check_permission(
    db: Session,
    user_id: int,
    tool_name: str,
    domain: Optional[str],
    permission_level: PermissionLevel,
    input_summary: Optional[str] = None,
    target_path: Optional[str] = None,
) -> GatewayResult:
    """The core gate. Every capability execution should call this before
    doing anything, and the result gets written to the audit log
    regardless of the outcome — that's what makes it an audit log rather
    than a debug log.
    """
    settings = get_or_create_settings(db, user_id)
    result = _evaluate(settings, domain, permission_level)

    _write_audit_entry(
        db, user_id, tool_name, domain, permission_level,
        result, input_summary, target_path,
    )
    return result


def _evaluate(settings: SecuritySettings, domain: Optional[str], permission_level: PermissionLevel) -> GatewayResult:
    if permission_level in ALWAYS_BLOCKED:
        return GatewayResult(GatewayDecision.BLOCKED, f"{permission_level.value} operations are blocked by default and cannot be enabled.")

    if not settings.computer_access_enabled:
        return GatewayResult(GatewayDecision.BLOCKED, "Computer access is turned off.")

    category_map = _CATEGORY_BY_DOMAIN.get(domain, {})
    category_attr = category_map.get(permission_level)

    if category_attr is None:
        # Unmapped domain/tier combination — fail closed rather than
        # silently allowing something nobody explicitly categorized.
        return GatewayResult(
            GatewayDecision.BLOCKED,
            f"No category mapping for domain='{domain}' at {permission_level.value} — defaulting to blocked."
        )

    if not getattr(settings, category_attr, False):
        return GatewayResult(GatewayDecision.BLOCKED, f"'{category_attr}' is turned off.")

    if CONFIRMATION_POLICY.get(permission_level, False):
        return GatewayResult(GatewayDecision.NEEDS_CONFIRMATION, f"{permission_level.value} operations require confirmation.")

    return GatewayResult(GatewayDecision.ALLOWED, "Allowed.")


def _write_audit_entry(
    db: Session,
    user_id: int,
    tool_name: str,
    domain: Optional[str],
    permission_level: PermissionLevel,
    result: GatewayResult,
    input_summary: Optional[str],
    target_path: Optional[str],
) -> None:
    try:
        entry = AuditLogEntry(
            user_id=user_id,
            tool_name=tool_name,
            domain=domain,
            permission_level=permission_level.value,
            decision=result.decision,
            reason=result.reason,
            input_summary=(input_summary or "")[:512] or None,
            target_path=(target_path or "")[:512] or None,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log entry — continuing without blocking the gateway decision")
        db.rollback()


def record_execution_outcome(db: Session, audit_entry_id: int, success: bool, error: Optional[str] = None) -> None:
    """Called after a capability actually runs, to fill in what happened.
    Best-effort — a failure here should never mask the real execution result.
    """
    try:
        entry = db.query(AuditLogEntry).filter(AuditLogEntry.id == audit_entry_id).first()
        if entry:
            entry.execution_status = "SUCCESS" if success else "FAILED"
            entry.execution_error = error
            db.commit()
    except Exception:
        logger.exception("Failed to record execution outcome on audit log entry")
        db.rollback()


# ---------------------------------------------------------------------------
# Allowed-areas path validation
# ---------------------------------------------------------------------------

def get_allowed_areas(settings: SecuritySettings) -> List[str]:
    try:
        return json.loads(settings.allowed_areas or "[]")
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Corrupt allowed_areas for settings id={settings.id}, treating as empty")
        return []


def check_path_allowed(db: Session, user_id: int, path: str) -> Tuple[bool, str]:
    """Resolves the path (following symlinks, collapsing '..') and checks
    it's genuinely inside one of the user's allowed areas — resolving
    first is what stops 'Documents/../../../etc/passwd' or a symlink
    planted inside an allowed folder from escaping it.

    Denied fragments are checked independently of allowed_areas: even if
    a user's own config mistakenly includes a sensitive path, this still
    blocks it.
    """
    settings = get_or_create_settings(db, user_id)

    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError) as e:
        return False, f"Could not resolve path: {e}"

    resolved_str = str(resolved).lower()
    for fragment in DENIED_PATH_FRAGMENTS:
        if fragment in resolved_str:
            return False, f"Path falls under a protected system location ('{fragment}')."

    allowed_areas = get_allowed_areas(settings)
    if not allowed_areas:
        return False, "No allowed areas configured — Antigen cannot access any files yet."

    for area in allowed_areas:
        try:
            area_resolved = Path(area).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if resolved == area_resolved or area_resolved in resolved.parents:
            return True, f"Inside allowed area: {area}"

    return False, "Path is not inside any allowed area."


# ---------------------------------------------------------------------------
# Trust classification
# ---------------------------------------------------------------------------

def classify_upload_trust() -> TrustLevel:
    """User uploads/attachments are UNTRUSTED by definition — see
    attachment_models.py's Attachment.trust_level, set at upload time.
    Kept here as the single source of truth for that default so it's
    documented in one place rather than hardcoded at each call site.
    """
    return TrustLevel.UNTRUSTED