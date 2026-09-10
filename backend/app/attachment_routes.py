"""API routes for file attachments.

Phase C1 (foundation): upload, list, metadata, download, delete.
Attachments are stored with status=UPLOADED. The Phase C2+ extraction
pipeline (PDF/DOCX/image/audio/etc.) will pick them up and move them
through PROCESSING -> PROCESSED, filling in extracted_text/embedding —
none of that logic lives here yet.
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .attachment_models import Attachment, AttachmentStatus
from .security_models import TrustLevel
from .attachment_security import (
    classify_and_validate, compute_sha256, generate_storage_path,
    AttachmentRejected, MAX_UPLOAD_SIZE_BYTES,
)
from .attachment_processing import process_attachment
from .auth import get_current_active_user
from .models import User, Conversation
from .db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments", tags=["attachments"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _read_with_limit(file: UploadFile) -> bytes:
    """Reads the upload in chunks, aborting as soon as the size cap is
    exceeded rather than buffering an arbitrarily large file into memory
    first. This is the actual DoS-relevant check; the size check inside
    classify_and_validate is a backstop for callers that pass raw bytes
    directly.
    """
    chunks = []
    total = 0
    chunk_size = 1024 * 1024  # 1MB
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds the upload size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("")
async def upload_attachment(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload a file. Optionally associate it with an existing conversation
    (ownership is verified — you cannot attach to someone else's conversation).
    """
    if conversation_id is not None:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

    content = await _read_with_limit(file)

    try:
        file_type, mime_type = classify_and_validate(file.filename, content)
    except AttachmentRejected as e:
        raise HTTPException(status_code=400, detail=str(e))

    checksum = compute_sha256(content)
    absolute_path, relative_path = generate_storage_path(current_user.id, file.filename)

    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        absolute_path.write_bytes(content)
    except OSError as e:
        logger.exception("Failed writing attachment to disk")
        raise HTTPException(status_code=500, detail="Could not save the uploaded file.") from e

    attachment = Attachment(
        user_id=current_user.id,
        conversation_id=conversation_id,
        filename=file.filename[:255],
        stored_path=relative_path,
        checksum_sha256=checksum,
        mime_type=mime_type,
        file_type=file_type,
        size_bytes=len(content),
        status=AttachmentStatus.UPLOADED,
        trust_level=TrustLevel.UNTRUSTED,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    background_tasks.add_task(process_attachment, attachment.id)

    logger.info(f"Attachment {attachment.id} uploaded by user {current_user.id} ({file_type.value}, {len(content)} bytes)")

    return _attachment_to_dict(attachment)


@router.get("")
def list_attachments(
    conversation_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Attachment).filter(Attachment.user_id == current_user.id)
    if conversation_id is not None:
        query = query.filter(Attachment.conversation_id == conversation_id)
    items = query.order_by(Attachment.created_at.desc()).limit(200).all()
    return {"items": [_attachment_to_dict(a) for a in items], "count": len(items)}


@router.get("/{attachment_id}")
def get_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    attachment = _get_owned_attachment(db, attachment_id, current_user.id)
    return _attachment_to_dict(attachment)


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from .config import settings

    attachment = _get_owned_attachment(db, attachment_id, current_user.id)
    absolute_path = Path(settings.UPLOAD_DIR) / attachment.stored_path
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="File is missing from storage.")

    return FileResponse(
        path=str(absolute_path),
        media_type=attachment.mime_type,
        filename=attachment.filename,
    )


@router.delete("/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from .config import settings

    attachment = _get_owned_attachment(db, attachment_id, current_user.id)
    absolute_path = Path(settings.UPLOAD_DIR) / attachment.stored_path
    absolute_path.unlink(missing_ok=True)

    db.delete(attachment)
    db.commit()
    return {"success": True, "message": "Attachment deleted."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_owned_attachment(db: Session, attachment_id: int, user_id: int) -> Attachment:
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.user_id == user_id,
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return attachment


def _attachment_to_dict(a: Attachment) -> dict:
    return {
        "id": a.id,
        "filename": a.filename,
        "conversation_id": a.conversation_id,
        "mime_type": a.mime_type,
        "file_type": a.file_type.value,
        "size_bytes": a.size_bytes,
        "status": a.status.value,
        "trust_level": a.trust_level.value,
        "created_at": a.created_at.isoformat(),
        "processed_at": a.processed_at.isoformat() if a.processed_at else None,
    }