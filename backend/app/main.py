from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import httpx
import json
import asyncio

from .config import settings
from .db import SessionLocal, init_db
from sqlalchemy.orm import Session
from .models import Conversation, Message as MessageModel, UserRole, User, Memory
from .services import (
    list_conversations as svc_list_conversations,
    delete_conversation as svc_delete_conversation,
    create_memory as svc_create_memory,
    get_memory as svc_get_memory,
    update_memory as svc_update_memory,
    delete_memory as svc_delete_memory,
    list_memories as svc_list_memories,
    semantic_search_memories as svc_semantic_search,
    generate_and_store_embedding as svc_generate_embedding,
    batch_generate_embeddings as svc_batch_generate,
)
from .auth import get_current_active_user, require_owner, create_access_token
from .auth_service import AuthService
from .voice import router as voice_router

app = FastAPI(title="Antigen API")

# Allow any localhost dev port (Vite shifts ports — 5173, 5174, 5175...
# when a previous instance is still holding one) instead of hardcoding one.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)

def build_system_prompt(user: User, db: Session, query_text: str | None = None) -> str:
    """Personalized system prompt for the current user, refreshed on every
    turn (not just new conversations) so name-addressing and memory recall
    stay present throughout a conversation, not just the opening message.

    When query_text is given (the user's current message), memory recall
    uses real semantic search — relevance-ranked against pgvector using a
    local Ollama embedding model, not just "most recent." Falls back to
    plain recency (list_memories) if semantic search errors for any reason
    (e.g. the embedding model isn't pulled yet), so a hiccup here never
    breaks the chat response itself.
    """
    name = user.display_name or user.username
    lines = [
        f"You are Antigen, {name}'s personal AI assistant.",
        f"{name} is your one and only primary user. You take direction only from them.",
        f"Address {name} by name where it feels natural, and speak as their own "
        f"private assistant rather than a generic chatbot.",
    ]

    memories = []
    try:
        if query_text:
            memories = svc_semantic_search(db=db, query_text=query_text, top_k=6, user_id=user.id)
        else:
            memories, _meta = svc_list_memories(db=db, page=1, page_size=8, user_id=user.id)
    except Exception:
        try:
            memories, _meta = svc_list_memories(db=db, page=1, page_size=8, user_id=user.id)
        except Exception:
            memories = []

    if memories:
        lines.append(f"\nWhat you currently know about {name} (weave in naturally; don't recite this list):")
        for m in memories:
            snippet = (m.get("content") or "").strip()
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            if snippet:
                lines.append(f"- {snippet}")

    return "\n".join(lines)


EXTRACTION_PROMPT = """You extract durable personal facts worth remembering long-term about a user, from one exchange of a conversation.

Rules:
- Only extract facts that are genuinely durable (preferences, ongoing projects, people in their life, decisions, recurring habits) — not one-off small talk, not the assistant's own reply content, not anything already obvious or trivial.
- If nothing durable was said, return an empty array.
- Each fact should be a short, self-contained sentence, written in third person about the user (e.g. "Prefers dark mode in all apps", not "I prefer dark mode").
- Output ONLY a JSON array of strings. No prose, no markdown, no explanation. Example: ["Works as a backend engineer", "Has a dog named Rex"]
"""

# Skip the extra extraction call entirely for messages that are almost
# certainly not going to contain a durable fact — this is what keeps
# Ollama from getting a second full call on every single trivial turn
# ("hi", "ok", "thanks"), not just a cheaper call.
_TRIVIAL_MESSAGES = {
    "hi", "hello", "hey", "yo", "ok", "okay", "k", "sure", "cool", "nice",
    "thanks", "thank you", "yes", "no", "yep", "nope", "bye", "goodbye",
}


def _worth_extracting(user_message: str) -> bool:
    text = user_message.strip().lower().rstrip("!.? ")
    if len(text) < 12:
        return False
    if text in _TRIVIAL_MESSAGES:
        return False
    return True


async def extract_and_save_memories(db: Session, user_id: int, user_message: str, assistant_reply: str) -> None:
    """Best-effort: ask the model whether this exchange contained anything
    worth remembering long-term, and save it as Memory rows if so, then
    generate a local embedding for each so semantic search can find it.
    Runs after the reply has already streamed back to the client, so any
    failure here (Ollama down, bad JSON, etc.) never affects the chat
    response itself — it's swallowed and logged only.

    Skipped entirely for short/trivial messages (see _worth_extracting) so
    this doesn't add a second Ollama call on every single turn — only on
    ones plausible enough to contain something durable.
    """
    if not _worth_extracting(user_message):
        return

    try:
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"User said: {user_message}\nAssistant replied: {assistant_reply}"},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload)
        if resp.status_code != 200:
            return

        raw = resp.json().get("message", {}).get("content", "").strip()
        # Models sometimes wrap JSON in ```json fences despite instructions — strip them.
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return

        for fact in facts:
            fact = str(fact).strip()
            if not fact:
                continue
            mem = svc_create_memory(db=db, type="fact", content=fact, source="auto", user_id=user_id)
            try:
                # Off the event loop — this is a sync DB+HTTP call and would
                # otherwise block other concurrent requests while it runs.
                await asyncio.to_thread(svc_generate_embedding, mem.id)
            except Exception:
                pass
    except Exception:
        # Extraction is a nice-to-have, not core to /chat working — never
        # let a parsing or connectivity hiccup here surface to the user.
        pass


# Auth request/response models
class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    model: str = "gpt-4o-mini"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()
    if settings.OPENAI_API_KEY:
        print("[startup] OPENAI_API_KEY loaded OK")
    else:
        print("[startup] WARNING: OPENAI_API_KEY is not set — /chat will fail with 500 until this is fixed")
    
    # Check if system is initialized
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            print("[startup] System not initialized. No users found. Visit /auth/register to create the first owner.")
        else:
            print(f"[startup] System initialized with {user_count} user(s)")
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ai/status")
async def ai_status():
    """Check AI provider status and available models."""
    status = {
        "backend": "ok",
        "ollama": {"reachable": False, "models": []},
        "openai": {"configured": bool(settings.OPENAI_API_KEY)}
    }

    # Check Ollama connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                status["ollama"]["reachable"] = True
                status["ollama"]["models"] = [model["name"] for model in data.get("models", [])]
                status["ollama"]["current_model"] = settings.OLLAMA_MODEL
    except Exception as e:
        status["ollama"]["error"] = str(e)

    return status


# --- Authentication Endpoints ---


@app.post("/auth/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user. Only allowed if no users exist yet (first owner setup)."""
    # Check if users already exist
    if db.query(User).count() > 0:
        raise HTTPException(status_code=400, detail="Registration is closed. System already initialized.")
    
    try:
        user = AuthService.initialize_first_owner(
            db=db,
            username=req.username,
            password=req.password,
            display_name=req.display_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    access_token = create_access_token(data={"sub": user.username})
    
    return AuthResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role.value
        }
    )


@app.post("/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password."""
    result = AuthService.login_user(db, req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    user, access_token = result
    
    return AuthResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role.value
        }
    )


@app.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current authenticated user information."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


@app.post("/chat")
async def chat(req: ChatRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Send a single new message and get the assistant's reply.

    Contract (this is what the frontend must send/expect):
      request:  { "message": "hi", "conversation_id": null | 123, "model": "gpt-4o-mini" }
      response: { "ok": true, "conversation_id": 123, "reply": "assistant text" }

    "model" selects the provider:
      - "gpt-4o-mini", "gpt-4o", etc. -> OpenAI's API (needs OPENAI_API_KEY)
      - "ollama:<model-name>" e.g. "ollama:llama3.2" -> local Ollama, no API key needed

    The server -- not the frontend -- is responsible for loading prior
    conversation history and building the full context sent to the model.
    Only the NEW user message is persisted here; the frontend does not
    need to (and should not) resend the whole transcript each turn.
    
    Conversations are now scoped to the authenticated user.
    """
    api_key = settings.OPENAI_API_KEY
    use_ollama = req.model.startswith("ollama:")

    if not use_ollama and not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    conv = None
    is_new = req.conversation_id is None
    if not is_new:
        conv = db.query(Conversation).filter(
            Conversation.id == req.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")

    if conv is None:
        conv = Conversation(user_id=current_user.id)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Load prior history so the model has context, without the frontend
    # needing to resend it (and without us re-storing duplicates).
    history = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conv.id)
        .order_by(MessageModel.created_at.asc())
        .all()
    )

    openai_messages = [{"role": "system", "content": build_system_prompt(current_user, db, query_text=req.message)}]
    openai_messages += [{"role": m.role, "content": m.content} for m in history]
    openai_messages.append({"role": "user", "content": req.message})

    # Persist only the new user message now.
    db.add(MessageModel(conversation_id=conv.id, role="user", content=req.message))
    db.commit()

    async def stream_response():
        assistant_text_parts = []

        if use_ollama:
            ollama_model = req.model.split("ollama:", 1)[1]
            url = f"{settings.OLLAMA_BASE_URL}/api/chat"
            payload = {"model": ollama_model, "messages": openai_messages, "stream": True}

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", url, json=payload) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            yield json.dumps(
                                {"error": f"Ollama error: {resp.status_code} {body.decode(errors='ignore')}"}
                            ) + "\n"
                            return
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            chunk = json.loads(line)
                            delta = chunk.get("message", {}).get("content", "")
                            if delta:
                                assistant_text_parts.append(delta)
                                yield json.dumps({"delta": delta}) + "\n"
                            if chunk.get("done"):
                                break
            except httpx.RequestError as e:
                yield json.dumps(
                    {"error": f"Could not reach Ollama at {settings.OLLAMA_BASE_URL} — is it running? ({e})"}
                ) + "\n"
                return
        else:
            # OpenAI's API is called normally (not token-streamed) for simplicity,
            # then sent down as a single delta so the frontend handles one format
            # regardless of provider.
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": req.model, "messages": openai_messages}

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, headers=headers, json=payload, timeout=60.0)
            except httpx.RequestError as e:
                yield json.dumps({"error": f"Could not reach OpenAI: {e}"}) + "\n"
                return

            if resp.status_code != 200:
                yield json.dumps({"error": f"OpenAI API error: {resp.status_code} {resp.text}"}) + "\n"
                return

            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            assistant_text_parts.append(text)
            yield json.dumps({"delta": text}) + "\n"

        full_text = "".join(assistant_text_parts)
        if full_text:
            # Use a fresh session here rather than the request-scoped `db` —
            # that dependency's lifecycle isn't guaranteed to still be open
            # by the time this generator resumes after the initial response
            # has already started streaming back to the client.
            save_db = SessionLocal()
            try:
                save_db.add(MessageModel(conversation_id=conv.id, role="assistant", content=full_text))
                save_db.commit()

                await extract_and_save_memories(
                    db=save_db,
                    user_id=current_user.id,
                    user_message=req.message,
                    assistant_reply=full_text,
                )
            finally:
                save_db.close()

        yield json.dumps({"done": True, "conversation_id": conv.id}) + "\n"

    return StreamingResponse(stream_response(), media_type="application/x-ndjson")


@app.get("/conversations")
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None, description="Search text appearing in messages (case-insensitive)"),
    date_from: datetime | None = Query(None, description="ISO datetime to filter conversations created at or after this"),
    date_to: datetime | None = Query(None, description="ISO datetime to filter conversations created at or before this"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        items, meta = svc_list_conversations(db=db, page=page, page_size=page_size, search=search, date_from=date_from, date_to=date_to, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"items": items, "meta": meta}


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
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
def delete_conversation_endpoint(conversation_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        if conversation_id <= 0:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid conversation ID."})

        # Verify the conversation belongs to the current user
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if not conv:
            return JSONResponse(status_code=404, content={"success": False, "message": "Conversation not found."})

        deleted = svc_delete_conversation(db=db, conversation_id=conversation_id)
        if not deleted:
            return JSONResponse(status_code=404, content={"success": False, "message": "Conversation not found."})

        return {"success": True, "message": "Conversation deleted successfully."}

    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    except Exception:
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
def create_memory_endpoint(payload: MemoryCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    if not payload.type or not payload.content:
        return JSONResponse(status_code=400, content={"success": False, "message": "type and content are required."})

    try:
        mem = svc_create_memory(db=db, type=payload.type, key=payload.key, content=payload.content, source=payload.source, tags=payload.tags, user_id=current_user.id)
        try:
            if background_tasks is not None:
                background_tasks.add_task(svc_generate_embedding, mem.id)
        except Exception:
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        items, meta = svc_list_memories(db=db, page=page, page_size=page_size, search=search, type=type, tags=tags, date_from=date_from, date_to=date_to, user_id=current_user.id)
        return {"items": items, "meta": meta}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.get("/memories/{memory_id}")
def get_memory_endpoint(memory_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        mem = db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.user_id == current_user.id
        ).first()
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
def update_memory_endpoint(memory_id: int, payload: MemoryUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        # Verify the memory belongs to the current user
        mem = db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.user_id == current_user.id
        ).first()
        if not mem:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        
        mem = svc_update_memory(db=db, memory_id=memory_id, **payload.dict())
        if not mem:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        return {"success": True, "memory": {"id": mem.id, "updated_at": mem.updated_at.isoformat() if mem.updated_at else None}}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.delete("/memories/{memory_id}")
def delete_memory_endpoint(memory_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        if memory_id <= 0:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid memory ID."})
        
        # Verify the memory belongs to the current user
        mem = db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.user_id == current_user.id
        ).first()
        if not mem:
            return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
        
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query_text = payload.get("query")
    if not query_text or not isinstance(query_text, str):
        raise HTTPException(status_code=400, detail="Payload must include a non-empty 'query' string.")
    try:
        results = svc_semantic_search(db=db, query_text=query_text, top_k=top_k, type=payload.get("type"), tags=payload.get("tags"), user_id=current_user.id)
        return {"items": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Embedding provider error")
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


@app.post("/memories/{memory_id}/embedding/retry")
def retry_embedding_endpoint(memory_id: int, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    mem = db.query(Memory).filter(
        Memory.id == memory_id,
        Memory.user_id == current_user.id
    ).first()
    if not mem:
        return JSONResponse(status_code=404, content={"success": False, "message": "Memory not found."})
    try:
        background_tasks.add_task(svc_generate_embedding, memory_id)
        return {"success": True, "message": "Embedding generation scheduled."}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to schedule embedding generation."})


@app.post("/memories/embeddings/batch")
def batch_embeddings_endpoint(limit: int = Query(100, ge=1, le=1000), background_tasks: BackgroundTasks = None, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        if background_tasks is not None:
            background_tasks.add_task(svc_batch_generate, limit, current_user.id)
            return {"success": True, "message": "Batch embedding job scheduled."}
        else:
            count = svc_batch_generate(limit, current_user.id)
            return {"success": True, "processed": count}
    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start batch job."})