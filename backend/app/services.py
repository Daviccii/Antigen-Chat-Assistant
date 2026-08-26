"""Database service helpers for conversations.

This module contains helpers to list conversations with pagination and
filtering. Queries are written to leverage indexed columns on
`Conversation.created_at` and `Message.conversation_id`/`Message.created_at`.

Functions:
  - list_conversations: returns paginated conversation summaries and meta.
"""
from typing import Optional, Tuple, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from .models import Conversation, Message, Memory
from .config import settings
import httpx
from sqlalchemy import text
from .db import SessionLocal
import logging

logger = logging.getLogger(__name__)
from .models import Memory

# Local embedding model served by Ollama — pull it once with:
#   ollama pull nomic-embed-text
# Produces 768-dim vectors, matching Memory.embedding's column type in
# models.py. If you change this, the column dimension needs to match and
# existing embeddings need regenerating.
EMBEDDING_MODEL = "nomic-embed-text"


def _get_local_embedding(text_input: str) -> list[float] | None:
    """Call Ollama's local embeddings endpoint. Returns None on failure
    rather than raising, so callers can decide how to degrade."""
    url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json={"model": EMBEDDING_MODEL, "prompt": text_input})
            resp.raise_for_status()
            return resp.json().get("embedding")
    except Exception as e:
        logger.warning("Local embedding request failed: %s", e)
        return None


def list_conversations(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user_id: Optional[int] = None,
) -> Tuple[List[Dict], Dict]:
    """Return a page of conversation summaries and pagination metadata.

    Args:
      db: SQLAlchemy session
      page: 1-based page number
      page_size: items per page
      search: optional substring to search in messages (case-insensitive)
      date_from: optional ISO datetime to filter conversation.created_at >= date_from
      date_to: optional ISO datetime to filter conversation.created_at <= date_to
      user_id: optional user ID to filter conversations by user

    Returns:
      (items, meta) where items is a list of dicts and meta contains pagination info.
    """

    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be between 1 and 200")

    # Base query for conversations
    q = db.query(Conversation)

    # Filter by user if provided
    if user_id:
        q = q.filter(Conversation.user_id == user_id)

    # If searching message text, join Message and filter by ILIKE.
    if search:
        q = q.join(Message).filter(Message.content.ilike(f"%{search}%"))

    if date_from:
        q = q.filter(Conversation.created_at >= date_from)
    if date_to:
        q = q.filter(Conversation.created_at <= date_to)

    # total distinct conversations matching filters
    total_q = q.statement.with_only_columns(func.count(func.distinct(Conversation.id))).order_by(None)
    total = db.execute(total_q).scalar() or 0

    total_pages = (total + page_size - 1) // page_size if total else 0

    # Fetch page of conversations (ordered by newest first)
    items_q = q.order_by(Conversation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    convs = items_q.all()

    results = []
    for c in convs:
        # Efficiently fetch last message for this conversation
        last = (
            db.query(Message)
            .filter(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .limit(1)
            .first()
        )
        # First user message doubles as a readable title, without needing a
        # dedicated `title` column (and the migration that would require).
        first_user_msg = (
            db.query(Message)
            .filter(Message.conversation_id == c.id, Message.role == "user")
            .order_by(Message.created_at.asc())
            .limit(1)
            .first()
        )
        title = None
        if first_user_msg and first_user_msg.content:
            title = first_user_msg.content.strip()
            if len(title) > 60:
                title = title[:60].rsplit(" ", 1)[0] + "…"

        results.append(
            {
                "id": c.id,
                "created_at": c.created_at.isoformat(),
                "last_message": last.content if last else None,
                "title": title,
            }
        )

    meta = {
        "total_items": int(total),
        "total_pages": int(total_pages),
        "current_page": int(page),
        "page_size": int(page_size),
    }

    return results, meta


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """Delete a conversation and its messages.

    Args:
        db: SQLAlchemy session
        conversation_id: id of the conversation to delete

    Returns:
        True if deleted, False if not found.

    Notes:
        - Uses ORM delete which will cascade to messages because of relationship cascade
        - Commits the transaction on success
    """
    if conversation_id is None or conversation_id <= 0:
        raise ValueError("conversation_id must be a positive integer")

    conv = db.get(Conversation, conversation_id)
    if not conv:
        return False

    db.delete(conv)
    db.commit()
    return True


def create_memory(db: Session, *, type: str, content: str, key: str | None = None, source: str | None = None, tags: str | None = None, user_id: int | None = None) -> Memory:
    """Create and persist a memory record.

    Returns the Memory ORM instance.
    """
    mem = Memory(type=type, key=key, content=content, source=source, tags=tags, user_id=user_id)
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def get_memory(db: Session, memory_id: int) -> Memory | None:
    return db.get(Memory, memory_id)


def update_memory(db: Session, memory_id: int, **fields) -> Memory | None:
    mem = db.get(Memory, memory_id)
    if not mem:
        return None
    for k, v in fields.items():
        if hasattr(mem, k) and v is not None:
            setattr(mem, k, v)
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def delete_memory(db: Session, memory_id: int) -> bool:
    mem = db.get(Memory, memory_id)
    if not mem:
        return False
    db.delete(mem)
    db.commit()
    return True


def list_memories(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    type: str | None = None,
    tags: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: int | None = None,
) -> tuple[list[dict], dict]:
    """List memories with pagination and simple filtering.

    - `search` matches `content` or `key` with ILIKE.
    - `tags` is a comma-separated list and will be matched with simple substring contains.
    - `user_id` filters memories by user.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 500:
        raise ValueError("page_size must be between 1 and 500")

    q = db.query(Memory)
    
    # Filter by user if provided
    if user_id:
        q = q.filter(Memory.user_id == user_id)
    
    if type:
        q = q.filter(Memory.type == type)
    if search:
        pat = f"%{search}%"
        q = q.filter((Memory.content.ilike(pat)) | (Memory.key.ilike(pat)))
    if tags:
        # simple contains check; can be improved with array/tags table later
        for t in [t.strip() for t in tags.split(",") if t.strip()]:
            q = q.filter(Memory.tags.ilike(f"%{t}%"))
    if date_from:
        q = q.filter(Memory.created_at >= date_from)
    if date_to:
        q = q.filter(Memory.created_at <= date_to)

    total_q = q.statement.with_only_columns(func.count(Memory.id)).order_by(None)
    total = db.execute(total_q).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total else 0

    items = q.order_by(Memory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    results = [
        {
            "id": m.id,
            "type": m.type,
            "key": m.key,
            "content": m.content,
            "source": m.source,
            "tags": m.tags,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in items
    ]

    meta = {"total_items": int(total), "total_pages": int(total_pages), "current_page": int(page), "page_size": int(page_size)}
    return results, meta


def semantic_search_memories(
    db: Session,
    query_text: str,
    top_k: int = 10,
    type: str | None = None,
    tags: str | None = None,
    user_id: int | None = None,
):
    """Semantic search over Memories using a local Ollama embedding model
    (nomic-embed-text) and pgvector nearest-neighbor search. Fully local —
    no external API calls, no API key needed.
    """
    emb = _get_local_embedding(query_text)
    if not emb:
        raise ValueError(
            "Could not generate a local embedding for the query — is Ollama running "
            f"with `{EMBEDDING_MODEL}` pulled? (ollama pull {EMBEDDING_MODEL})"
        )

    vec_literal = "[" + ",".join(f"{float(x):.12f}" for x in emb) + "]"

    # Only rank rows that actually have an embedding yet — a freshly created
    # memory whose background embedding job hasn't run should be skipped
    # rather than sorting unpredictably against a NULL vector.
    where_clauses = ["embedding IS NOT NULL"]
    params = {"limit": int(top_k)}
    if user_id:
        where_clauses.append("user_id = :user_id")
        params["user_id"] = user_id
    if type:
        where_clauses.append("type = :type")
        params["type"] = type
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for i, t in enumerate(tag_list):
            key = f"tag_{i}"
            where_clauses.append(f"tags ILIKE :{key}")
            params[key] = f"%{t}%"

    where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = text(
        f"SELECT id, type, key, content, source, tags, created_at, updated_at, embedding <-> '{vec_literal}' AS distance "
        f"FROM memories {where_sql} ORDER BY distance ASC LIMIT :limit"
    )

    rows = db.execute(sql, params).fetchall()
    results = []
    for r in rows:
        results.append(
            {
                "id": r[0],
                "type": r[1],
                "key": r[2],
                "content": r[3],
                "source": r[4],
                "tags": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "distance": float(r[8]) if r[8] is not None else None,
            }
        )

    return results


def generate_and_store_embedding(memory_id: int) -> None:
    """Generate a local embedding for a memory and store it in the DB.

    This function creates its own DB session and is safe to run in a
    background task (or via asyncio.to_thread from async code). Errors are
    logged and do not raise to callers.
    """
    db = SessionLocal()
    try:
        mem = db.get(Memory, memory_id)
        if not mem:
            logger.warning("Memory id %s not found for embedding generation", memory_id)
            return
        if mem.embedding is not None:
            logger.debug("Memory id %s already has embedding; skipping", memory_id)
            return

        emb = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            emb = _get_local_embedding(mem.content)
            if emb:
                break
            logger.warning("Embedding attempt %s failed for memory %s; retrying", attempt, memory_id)

        if not emb:
            logger.error("Failed to obtain local embedding after %s attempts for memory %s", max_attempts, memory_id)
            return

        try:
            mem.embedding = emb
            db.add(mem)
            db.commit()
            logger.info("Stored embedding for memory id %s", memory_id)
        except Exception:
            logger.exception("Failed to store embedding for memory id %s", memory_id)
            db.rollback()
    finally:
        db.close()


def batch_generate_embeddings(limit: int | None = None, user_id: int | None = None) -> int:
    """Batch generate embeddings for memories missing them.

    Args:
      limit: optional max number of memories to process in this batch.
      user_id: optional user ID to filter memories by user.

    Returns:
      Number of memories processed (attempted).
    """
    db = SessionLocal()
    try:
        q = db.query(Memory).filter(Memory.embedding == None)
        if user_id:
            q = q.filter(Memory.user_id == user_id)
        q = q.order_by(Memory.created_at.asc())
        if limit:
            q = q.limit(limit)
        to_process = q.all()
        count = 0
        for m in to_process:
            try:
                generate_and_store_embedding(m.id)
            except Exception:
                logger.exception("Error generating embedding for memory %s", m.id)
            count += 1
        return count
    finally:
        db.close()