"""Security and classification for uploaded attachments.

Nothing here trusts client-supplied data: not the filename, not the
declared Content-Type, not the extension. Real file type is sniffed
from the actual bytes via libmagic, and every on-disk name is a
server-generated UUID so path traversal / overwrite tricks via a
crafted filename ("../../etc/passwd", "shell.php.png") are structurally
impossible — the original name is stored only as metadata, never used
to build a path.
"""
import hashlib
import uuid
from pathlib import Path
from typing import Tuple

import magic  # python-magic — requires libmagic (see requirements notes)

from .attachment_models import AttachmentType
from .config import settings

# Extension is only used as a hint for AttachmentType classification and
# as a sanity cross-check against the sniffed MIME type below — it is
# NEVER trusted on its own to decide what a file is.
EXTENSION_TYPE_MAP = {
    ".jpg": AttachmentType.IMAGE, ".jpeg": AttachmentType.IMAGE,
    ".png": AttachmentType.IMAGE, ".webp": AttachmentType.IMAGE,
    ".gif": AttachmentType.IMAGE, ".heic": AttachmentType.IMAGE,
    ".pdf": AttachmentType.PDF,
    ".docx": AttachmentType.DOCX,
    ".xlsx": AttachmentType.SPREADSHEET, ".xls": AttachmentType.SPREADSHEET,
    ".csv": AttachmentType.SPREADSHEET,
    ".mp3": AttachmentType.AUDIO, ".wav": AttachmentType.AUDIO,
    ".m4a": AttachmentType.AUDIO, ".ogg": AttachmentType.AUDIO,
    ".mp4": AttachmentType.VIDEO, ".mov": AttachmentType.VIDEO,
    ".webm": AttachmentType.VIDEO, ".mkv": AttachmentType.VIDEO,
    ".py": AttachmentType.CODE, ".js": AttachmentType.CODE, ".jsx": AttachmentType.CODE,
    ".ts": AttachmentType.CODE, ".tsx": AttachmentType.CODE, ".java": AttachmentType.CODE,
    ".c": AttachmentType.CODE, ".cpp": AttachmentType.CODE, ".go": AttachmentType.CODE,
    ".rs": AttachmentType.CODE, ".rb": AttachmentType.CODE, ".php": AttachmentType.CODE,
    ".sql": AttachmentType.CODE, ".json": AttachmentType.CODE, ".yaml": AttachmentType.CODE,
    ".yml": AttachmentType.CODE, ".html": AttachmentType.CODE, ".css": AttachmentType.CODE,
    ".sh": AttachmentType.CODE, ".md": AttachmentType.CODE, ".txt": AttachmentType.CODE,
}

# Real MIME types (as sniffed from content, not the extension) that we
# accept per AttachmentType. Anything not in here is rejected outright —
# this is an allow-list, not a block-list, which is what makes it safe
# against file types we didn't think to explicitly ban.
ALLOWED_MIME_BY_TYPE = {
    AttachmentType.IMAGE: {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"},
    AttachmentType.PDF: {"application/pdf"},
    AttachmentType.DOCX: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",  # docx is a zip container; python-magic sometimes reports this
    },
    AttachmentType.SPREADSHEET: {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv", "text/plain", "application/zip",
    },
    AttachmentType.AUDIO: {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/ogg", "audio/x-m4a"},
    AttachmentType.VIDEO: {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"},
    AttachmentType.CODE: {"text/plain", "text/x-python", "application/json", "text/html", "text/css",
                           "text/x-shellscript", "text/x-c", "text/x-java", "application/x-yaml"},
}

# Explicit deny-list as a second layer even though the allow-list above
# already excludes these — belt and suspenders against anything that
# could ever be interpreted as executable by the OS or a browser.
DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".com", ".msi",
    ".scr", ".jar", ".app", ".apk", ".ps1", ".vbs", ".wsf",
}

MAX_UPLOAD_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class AttachmentRejected(ValueError):
    """Raised for any validation failure — caller maps this to HTTP 400/413."""


def classify_and_validate(original_filename: str, content: bytes) -> Tuple[AttachmentType, str]:
    """Sniff the real file type from bytes and validate it against what
    the extension claims to be. Returns (AttachmentType, sniffed_mime_type)
    or raises AttachmentRejected.
    """
    if len(content) == 0:
        raise AttachmentRejected("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise AttachmentRejected(
            f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit."
        )

    ext = Path(original_filename).suffix.lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise AttachmentRejected(f"File type '{ext}' is not allowed.")

    claimed_type = EXTENSION_TYPE_MAP.get(ext)
    if claimed_type is None:
        raise AttachmentRejected(f"Unsupported file extension: '{ext}'.")

    sniffed_mime = magic.from_buffer(content, mime=True)

    allowed_mimes = ALLOWED_MIME_BY_TYPE.get(claimed_type, set())
    if sniffed_mime not in allowed_mimes:
        raise AttachmentRejected(
            f"File content ({sniffed_mime}) does not match its extension ({ext}). "
            "The file may be mislabeled or corrupted."
        )

    return claimed_type, sniffed_mime


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_storage_path(user_id: int, original_filename: str) -> Tuple[Path, str]:
    """Returns (absolute_disk_path, relative_stored_path). The on-disk
    filename is always a fresh UUID + the validated extension — the
    original filename is never used to build a path.
    """
    ext = Path(original_filename).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    relative_path = f"{user_id}/{stored_name}"
    absolute_path = Path(settings.UPLOAD_DIR) / str(user_id) / stored_name
    return absolute_path, relative_path