import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx

from .config import settings
from .db import SessionLocal, init_db
from sqlalchemy.orm import Session
from .models import Conversation, Message as MessageModel
from .services import list_conversations as svc_list_conversations, delete_conversation as svc_delete_conversation
from .services import (
    create_memory as svc_create_memory,
    get_memory as svc_get_memory,
    update_memory as svc_update_memory,
    delete_memory as svc_delete_memory,
    list_memories as svc_list_memories,
    semantic_search_memories as svc_semantic_search,
    generate_and_store_embedding as svc_generate_embedding,
    batch_generate_embeddings as svc_batch_generate,
)
from fastapi import BackgroundTasks
import httpx
from fastapi import Query
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi import Query
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("antigen.chat")

app = FastAPI(title="Antigen API")

# Allow local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = "gpt-3.5-turbo"
    conversation_id: Optional[int] = None


def _is_configured_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    normalized = api_key.strip()
    if not normalized:
        return False
    if normalized.lower() in {"your_openai_api_key_here", "replace_me", "changeme"}:
        return False
    if normalized.startswith("sk-") or normalized.startswith("sk-proj-") or normalized.startswith("gsk_"):
        return True
    return False


def build_demo_reply(messages: List[Message]) -> str:
    last_user_message = ""
    for message in reversed(messages):
        if message.role == "user" and message.content:
            last_user_message = message.content.strip()
            break

    if last_user_message:
        return (
            "Demo mode: I’m ready to help. Add a real OPENAI_API_KEY in backend/.env and restart the backend "
            f"to enable live replies. Your last message was: {last_user_message}"
        )

    return (
        "Demo mode: I’m ready to help. Add a real OPENAI_API_KEY in backend/.env and restart the backend "
        "to enable live replies."
    )


def get_db():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    logger.info("Incoming chat request: %s", req.dict())

    api_key = settings.OPENAI_API_KEY
    logger.info("OPENAI_API_KEY loaded: %s", bool(api_key))
    logger.info("OPENAI_API_KEY value: %s", api_key)
    if not _is_configured_api_key(api_key):
        logger.warning("OPENAI_API_KEY is missing or placeholder; returning demo reply")
        demo_reply = build_demo_reply(req.messages)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "assistant_message": demo_reply, "demo": True, "detail": "OPENAI_API_KEY not set; using demo reply"},
        )

    conv = None
    if req.conversation_id:
        conv = db.query(Conversation).get(req.conversation_id)
        logger.info("Using existing conversation_id=%s", req.conversation_id)

    if not conv:
        conv = Conversation()
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("Created new conversation_id=%s", conv.id)

    for m in req.messages:
        logger.info("Persisting message for conversation_id=%s role=%s content=%s", conv.id, m.role, m.content)
        msg = MessageModel(conversation_id=conv.id, role=m.role, content=m.content)
        db.add(msg)
    db.commit()

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": req.model or "gpt-3.5-turbo", "messages": [m.dict() for m in req.messages]}
    logger.info("Prompt sent to model model=%s payload=%s", payload.get("model"), payload)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=60.0)
            logger.info("Raw provider response status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.exception("OpenAI provider request failed with status=%s body=%s", exc.response.status_code, exc.response.text)
        return JSONResponse(status_code=502, content={"ok": False, "error": "OpenAI provider request failed", "detail": f"{exc.response.status_code} {exc.response.text}"})
    except Exception as exc:
        logger.exception("OpenAI provider request raised an exception")
        return JSONResponse(status_code=502, content={"ok": False, "error": "OpenAI provider request failed", "detail": str(exc)})

    assistant_text = None
    try:
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            assistant_text = message.get("content")
            if isinstance(assistant_text, list):
                assistant_text = "".join(part.get("text", "") for part in assistant_text if isinstance(part, dict))
            if isinstance(assistant_text, str):
                assistant_text = assistant_text.strip()
        if not assistant_text:
            assistant_text = (data.get("message") or {}).get("content") if isinstance(data.get("message"), dict) else None
            if isinstance(assistant_text, list):
                assistant_text = "".join(part.get("text", "") for part in assistant_text if isinstance(part, dict))
            if isinstance(assistant_text, str):
                assistant_text = assistant_text.strip()
    except Exception as exc:
        logger.exception("Failed to parse assistant message from provider response")
        return JSONResponse(status_code=502, content={"ok": False, "error": "Failed to parse assistant response", "detail": str(exc)})

    logger.info("Parsed assistant response=%s", assistant_text)
    if not assistant_text:
        logger.error("Provider returned no assistant message payload=%s", data)
        return JSONResponse(status_code=502, content={"ok": False, "error": "Provider returned no assistant message", "detail": data})

    assistant_msg = MessageModel(conversation_id=conv.id, role="assistant", content=assistant_text)
    db.add(assistant_msg)
    db.commit()
    logger.info("Saved assistant message to conversation_id=%s", conv.id)

    response_payload = {"ok": True, "conversation_id": conv.id, "assistant_message": assistant_text, "data": data, "model": payload.get("model")}
    logger.info("Final API response returned to frontend: %s", response_payload)
    return response_payload


@app.get("/conversations")
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None, description="Search text appearing in messages (case-insensitive)"),
    date_from: datetime | None = Query(None, description="ISO datetime to filter conversations created at or after this"),
    date_to: datetime | None = Query(None, description="ISO datetime to filter conversations created at or before this"),
    db: Session = Depends(get_db),
):
    """List conversations with pagination and optional filtering.

    Returns items and a `meta` object containing pagination info.
    """

    try:
        items, meta = svc_list_conversations(db=db, page=page, page_size=page_size, search=search, date_from=date_from, date_to=date_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"items": items, "meta": meta}


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in db.query(MessageModel).filter(MessageModel.conversation_id == conv.id).order_by(MessageModel.created_at.asc()).all()
    ]

    return {"id": conv.id, "created_at": conv.created_at.isoformat(), "messages": messages}


@app.delete("/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation and its messages.

    Returns a JSON success message on deletion, or a 404 JSON response if not found.
    """
    # Validate ID
    try:
        if conversation_id <= 0:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid conversation ID."})

        deleted = svc_delete_conversation(db=db, conversation_id=conversation_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"success": False, "message": "Conversation not found."})

        return {"success": True, "message": "Conversation deleted successfully."}

    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    except Exception as e:
        # Prevent internal errors from crashing the server; return a 500 with a simple message.
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


# --- Memory APIs ---


class MemoryCreate(BaseModel):
    type: str
    content: str
    key: str | None = None
    source: str | None = None
    tags: str | None = None


class MemoryUpdate(BaseModel):
    content: str | None = None
    key: str | None = None
    source: str | None = None
    tags: str | None = None


@app.post("/memories")
def create_memory_endpoint(payload: MemoryCreate, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    # Validate minimal fields
    if not payload.type or not payload.content:
        return JSONResponse(status_code=400, content={"success": False, "message": "type and content are required."})

    try:
        mem = svc_create_memory(db=db, type=payload.type, key=payload.key, content=payload.content, source=payload.source, tags=payload.tags)
        # Schedule background embedding generation if missing
        try:
            if background_tasks is not None:
                background_tasks.add_task(svc_generate_embedding, mem.id)
        except Exception:
            # If background task scheduling fails, continue; embedding can be generated later
            pass

        return {"success": True, "memory": {"id": mem.id, "type": mem.type, "key": mem.key, "created_at": mem.created_at.isoformat()}}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.get("/memories")
def list_memories_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: str | None = Query(None),
    type: str | None = Query(None),
    tags: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        items, meta = svc_list_memories(db=db, page=page, page_size=page_size, search=search, type=type, tags=tags, date_from=date_from, date_to=date_to)
        return {"items": items, "meta": meta}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.get("/memories/{memory_id}")
def get_memory_endpoint(memory_id: int, db: Session = Depends(get_db)):
    try:
        mem = svc_get_memory(db=db, memory_id=memory_id)
        if not mem:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        return {
            "id": mem.id,
            "type": mem.type,
            "key": mem.key,
            "content": mem.content,
            "source": mem.source,
            "tags": mem.tags,
            "created_at": mem.created_at.isoformat(),
            "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
        }
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.put("/memories/{memory_id}")
def update_memory_endpoint(memory_id: int, payload: MemoryUpdate, db: Session = Depends(get_db)):
    try:
        mem = svc_update_memory(db=db, memory_id=memory_id, **payload.dict())
        if not mem:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        return {"success": True, "memory": {"id": mem.id, "updated_at": mem.updated_at.isoformat() if mem.updated_at else None}}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.delete("/memories/{memory_id}")
def delete_memory_endpoint(memory_id: int, db: Session = Depends(get_db)):
    try:
        if memory_id <= 0:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid memory ID."})
        deleted = svc_delete_memory(db=db, memory_id=memory_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        return {"success": True, "message": "Memory deleted successfully."}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.post("/memories/semantic_search")
def semantic_search_endpoint(
    payload: dict,
    top_k: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Semantic search memories using embeddings + pgvector.

    Payload must be: { "query": "some text", "type": "optional", "tags": "comma,separated" }
    Returns a list of memories ordered by distance (lower is more similar).
    """
    query_text = payload.get("query")
    if not query_text or not isinstance(query_text, str):
        raise HTTPException(status_code=400, detail="Payload must include a non-empty 'query' string.")
    try:
        results = semantic_results = svc_semantic_search(db=db, query_text=query_text, top_k=top_k, type=payload.get("type"), tags=payload.get("tags"))
        return {"items": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Embedding provider error")
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.post("/memories/{memory_id}/embedding/retry")
def retry_embedding_endpoint(memory_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger embedding generation for a single memory (background).

    Useful for manual recovery when embedding generation previously failed.
    """
    mem = svc_get_memory(db=db, memory_id=memory_id)
    if not mem:
        return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
    try:
        background_tasks.add_task(svc_generate_embedding, memory_id)
        return {"success": True, "message": "Embedding generation scheduled."}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to schedule embedding generation."})


@app.post("/memories/embeddings/batch")
def batch_embeddings_endpoint(limit: int = Query(100, ge=1, le=1000), background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    """Schedule a background batch job to generate embeddings for missing memories.

    Returns the number scheduled (best-effort).
    """
    try:
        # Schedule batch in background so API returns quickly
        if background_tasks is not None:
            background_tasks.add_task(svc_batch_generate, limit)
            return {"success": True, "message": "Batch embedding job scheduled."}
        else:
            # If no background tasks, run synchronously
            count = svc_batch_generate(limit)
            return {"success": True, "processed": count}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start batch job."})
