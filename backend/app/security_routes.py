"""API routes for the Security Gateway: settings (kill switch + allowed
areas) and the audit log. No capability execution lives here — this is
purely the control panel described in design doc section 10.
"""
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .security_models import SecuritySettings, AuditLogEntry
from .security_gateway import get_or_create_settings, get_allowed_areas, check_path_allowed
from .auth import get_current_active_user
from .models import User
from .db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SecuritySettingsUpdate(BaseModel):
    computer_access_enabled: Optional[bool] = None
    file_read_enabled: Optional[bool] = None
    file_modification_enabled: Optional[bool] = None
    application_control_enabled: Optional[bool] = None
    system_control_enabled: Optional[bool] = None
    admin_operations_enabled: Optional[bool] = None
    trading_enabled: Optional[bool] = None
    cybersecurity_enabled: Optional[bool] = None


class AllowedAreaRequest(BaseModel):
    path: str


@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db, current_user.id)
    return _settings_to_dict(settings)


@router.put("/settings")
def update_settings(
    payload: SecuritySettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db, current_user.id)

    updates = payload.dict(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    logger.info(f"User {current_user.id} updated security settings: {updates}")
    return _settings_to_dict(settings)


@router.get("/allowed-areas")
def list_allowed_areas(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db, current_user.id)
    return {"areas": get_allowed_areas(settings)}


@router.post("/allowed-areas")
def add_allowed_area(
    payload: AllowedAreaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Adds a path to the user's allowed areas. Rejects anything that
    would resolve into a protected system location outright — the same
    DENIED_PATH_FRAGMENTS check used at execution time, applied here too
    so a bad area can't even be saved in the first place.
    """
    from .security_gateway import DENIED_PATH_FRAGMENTS
    from pathlib import Path

    try:
        resolved = str(Path(payload.path).expanduser().resolve())
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve path: {e}")

    resolved_lower = resolved.lower()
    for fragment in DENIED_PATH_FRAGMENTS:
        if fragment in resolved_lower:
            raise HTTPException(status_code=400, detail=f"This path falls under a protected system location ('{fragment}') and cannot be added.")

    settings = get_or_create_settings(db, current_user.id)
    areas = get_allowed_areas(settings)
    if resolved not in areas:
        areas.append(resolved)
        settings.allowed_areas = json.dumps(areas)
        db.commit()

    return {"areas": areas}


@router.delete("/allowed-areas")
def remove_allowed_area(
    payload: AllowedAreaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db, current_user.id)
    areas = get_allowed_areas(settings)
    areas = [a for a in areas if a != payload.path]
    settings.allowed_areas = json.dumps(areas)
    db.commit()
    return {"areas": areas}


@router.get("/audit-log")
def list_audit_log(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    limit = min(limit, 500)
    entries = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.user_id == current_user.id)
        .order_by(AuditLogEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": e.id,
                "tool_name": e.tool_name,
                "domain": e.domain,
                "permission_level": e.permission_level,
                "decision": e.decision.value,
                "reason": e.reason,
                "input_summary": e.input_summary,
                "target_path": e.target_path,
                "execution_status": e.execution_status,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "count": len(entries),
    }


def _settings_to_dict(settings: SecuritySettings) -> dict:
    return {
        "computer_access_enabled": settings.computer_access_enabled,
        "file_read_enabled": settings.file_read_enabled,
        "file_modification_enabled": settings.file_modification_enabled,
        "application_control_enabled": settings.application_control_enabled,
        "system_control_enabled": settings.system_control_enabled,
        "admin_operations_enabled": settings.admin_operations_enabled,
        "trading_enabled": settings.trading_enabled,
        "cybersecurity_enabled": settings.cybersecurity_enabled,
        "allowed_areas": get_allowed_areas(settings),
    }