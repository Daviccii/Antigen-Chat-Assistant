"""Context Engine - Phase 3 Context Building Service.

This service builds comprehensive context for LLM requests by combining:
- Current time (from TimeService)
- User profile and preferences
- Relevant long-term memories
- Project context
- Conversation summary
- Recent messages

The context engine ensures Llama receives accurate, authoritative context
rather than inventing information.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import time
import logging

from .models import User, Memory, Project
from .time_service import TimeService
from .memory_service import (
    MemoryService,
    MemoryCategory,
    MemoryImportance,
    MemorySource
)

logger = logging.getLogger(__name__)


class ContextEngine:
    """Comprehensive context building for LLM requests."""
    
    @staticmethod
    def build_full_context(
        db: Session,
        user: User,
        query_text: Optional[str] = None,
        conversation_id: Optional[int] = None,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build complete context for LLM request."""
        start_time = time.time()
        
        # 1. Time Context (Authoritative)
        time_start = time.time()
        time_context = TimeService.get_time_context(user.timezone or "Africa/Nairobi")
        logger.debug(f"Time context built in {time.time() - time_start:.3f}s")
        
        # 2. User Profile Context
        user_start = time.time()
        user_profile = ContextEngine._build_user_profile(user)
        logger.debug(f"User profile built in {time.time() - user_start:.3f}s")
        
        # 3. Memory Context
        memory_start = time.time()
        memory_context = ContextEngine._build_memory_context(
            db, user.id, query_text, project_id
        )
        logger.debug(f"Memory context built in {time.time() - memory_start:.3f}s")
        
        # 4. Project Context
        project_start = time.time()
        project_context = ContextEngine._build_project_context(db, user.id, project_id)
        logger.debug(f"Project context built in {time.time() - project_start:.3f}s")
        
        # 5. Conversation Context
        conv_start = time.time()
        conversation_context = ContextEngine._build_conversation_context(
            db, user.id, conversation_id
        )
        logger.debug(f"Conversation context built in {time.time() - conv_start:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"Total context building time: {total_time:.3f}s")
        
        return {
            "time": time_context,
            "user_profile": user_profile,
            "memories": memory_context,
            "projects": project_context,
            "conversation": conversation_context,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _build_user_profile(user: User) -> Dict[str, Any]:
        """Build user profile context."""
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "timezone": user.timezone,
            "role": user.role.value if user.role else None,
            "is_active": user.is_active
        }
    
    @staticmethod
    def _build_memory_context(
        db: Session,
        user_id: int,
        query_text: Optional[str] = None,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build memory context with intelligent retrieval."""
        
        # Only retrieve memories when we have a query to match against
        # This avoids unnecessary database queries for simple greetings
        if not query_text or len(query_text.strip()) < 10:
            # For short messages, only get critical user profile info
            profile_memories = MemoryService.get_user_memories(
                db, user_id, category=MemoryCategory.USER_PROFILE, limit=3
            )
            
            return {
                "profile_memories": [
                    {
                        "content": m.content,
                        "confidence": m.confidence,
                        "last_confirmed": m.last_confirmed_at.isoformat() if m.last_confirmed_at else None
                    }
                    for m in profile_memories
                ],
                "explicit_memories": [],
                "preferences": [],
                "relevant_memories": []
            }
        
        # For substantive queries, retrieve relevant memories more efficiently
        # Combine retrieval into fewer queries
        relevant_memories = []
        if query_text:
            relevant_memories = MemoryService.retrieve_relevant_memories(
                db, user_id, query_text, project_id=project_id, limit=5  # Reduced from 8
            )
        
        # Only get explicit memories if they're highly important
        explicit_memories = MemoryService.get_user_memories(
            db, user_id, category=MemoryCategory.EXPLICIT, limit=5  # Reduced from 10
        )
        
        # Preferences are important but keep limit reasonable
        preference_memories = MemoryService.get_user_memories(
            db, user_id, category=MemoryCategory.PREFERENCE, limit=3  # Reduced from 5
        )
        
        return {
            "profile_memories": [],  # Skip profile for complex queries, focus on relevant
            "explicit_memories": [
                {
                    "content": m.content,
                    "importance": m.importance,
                    "confidence": m.confidence
                }
                for m in explicit_memories
            ],
            "preferences": [
                {
                    "content": m.content,
                    "confidence": m.confidence
                }
                for m in preference_memories
            ],
            "relevant_memories": relevant_memories
        }
    
    @staticmethod
    def _build_project_context(
        db: Session,
        user_id: int,
        project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build project context - optimized to only load when necessary."""
        
        # Only load project context if a specific project is requested
        # This avoids loading all projects on every request
        if not project_id:
            return {"all_projects": []}
        
        # Load only the specific project requested by ID
        from .models import Project
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            return {"all_projects": []}
        
        # Only load memories for this specific project, with limited count
        project_memories = MemoryService.get_user_memories(
            db, user_id, project_id=project.id, limit=5  # Reduced from 10
        )
        
        project_details = [{
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "memory_count": len(project_memories),
            "key_memories": [
                {
                    "content": m.content,
                    "importance": m.importance
                }
                for m in project_memories[:3]  # Reduced from 5
            ]
        }]
        
        return {
            "current_project": project_details[0],
            "all_projects": project_details
        }
    
    @staticmethod
    def _build_conversation_context(
        db: Session,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build conversation context - optimized to limit history loading."""
        from .models import Conversation, Message as MessageModel
        
        if not conversation_id:
            return {"has_active_conversation": False}
        
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            return {"has_active_conversation": False}
        
        # Only load recent messages instead of entire history
        # This is the key optimization - limit to last 6 messages (3 exchanges)
        messages = (
            db.query(MessageModel)
            .filter(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at.desc())
            .limit(6)
            .all()
        )
        
        # Reverse to get chronological order
        messages = list(reversed(messages))
        
        recent_messages = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.created_at.isoformat()
            }
            for m in messages
        ]
        
        return {
            "has_active_conversation": True,
            "conversation_id": conversation.id,
            "message_count": len(messages),
            "recent_messages": recent_messages,
            "summary": None  # Removed summary generation for performance
        }
    
    @staticmethod
    def _generate_conversation_summary(messages) -> str:
        """Generate a simple conversation summary."""
        # This is a basic implementation - could be enhanced with LLM summarization
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]
        
        return f"Conversation with {len(user_messages)} user messages and {len(assistant_messages)} assistant responses."
    
    @staticmethod
    def format_context_for_llm(context: Dict[str, Any]) -> str:
        """Format context as structured text for LLM system prompt."""
        lines = []
        
        # Time Context
        time = context["time"]
        lines.append("CURRENT TIME (AUTHORITATIVE):")
        lines.append(f"- Local time: {time['local']} ({time['timezone']})")
        lines.append(f"- UTC time: {time['utc']}")
        lines.append(f"- Date: {time['date']}")
        lines.append(f"- Weekday: {time['weekday']}")
        lines.append("")
        
        # User Profile
        user = context["user_profile"]
        lines.append("USER PROFILE:")
        lines.append(f"- Name: {user['display_name']}")
        lines.append(f"- Timezone: {user['timezone']}")
        lines.append("")
        
        # User Preferences
        preferences = context["memories"]["preferences"]
        if preferences:
            lines.append("USER PREFERENCES:")
            for pref in preferences:
                lines.append(f"- {pref['content']}")
            lines.append("")
        
        # Relevant Memories
        relevant = context["memories"]["relevant_memories"]
        if relevant:
            lines.append("RELEVANT MEMORIES:")
            for mem in relevant:
                lines.append(f"- {mem['content']} (confidence: {mem['confidence']:.2f})")
            lines.append("")
        
        # Project Context
        projects = context["projects"].get("current_project") or context["projects"].get("all_projects", [])
        if projects:
            lines.append("PROJECT CONTEXT:")
            if isinstance(projects, dict):
                # Single project
                lines.append(f"- Project: {projects['name']}")
                if projects.get("description"):
                    lines.append(f"  Description: {projects['description']}")
                for mem in projects.get("key_memories", []):
                    lines.append(f"  - {mem['content']}")
            else:
                # Multiple projects
                for project in projects[:3]:  # Limit to top 3 projects
                    lines.append(f"- Project: {project['name']}")
                    for mem in project.get("key_memories", [])[:3]:
                        lines.append(f"  - {mem['content']}")
            lines.append("")
        
        # Conversation Context
        conv = context["conversation"]
        if conv.get("has_active_conversation"):
            lines.append("CONVERSATION CONTEXT:")
            if conv.get("summary"):
                lines.append(f"- Summary: {conv['summary']}")
            lines.append(f"- Recent messages: {conv['message_count']}")
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def process_user_message(
        db: Session,
        user_id: int,
        user_message: str,
        assistant_response: str
    ) -> Dict[str, Any]:
        """Process user message for memory extraction and updates."""
        results = {
            "memories_created": [],
            "memories_updated": [],
            "corrections_handled": []
        }
        
        # Detect memory commands
        command = MemoryService.detect_memory_command(user_message)
        if command["is_command"]:
            if command["command_type"] == "remember":
                memory = MemoryService.create_memory(
                    db=db,
                    user_id=user_id,
                    content=command["content"],
                    category=MemoryCategory.EXPLICIT,
                    source=MemorySource.USER_EXPLICIT,
                    importance=MemoryImportance.HIGH,
                    confidence=0.9
                )
                results["memories_created"].append(memory.id)
            
            elif command["command_type"] == "forget":
                # Find and delete relevant memories
                similar = MemoryService.find_similar_memories(db, user_id, command["content"], threshold=0.7, limit=5)
                for memory in similar:
                    MemoryService.delete_memory(db, memory.id, user_id)
                    results["memories_updated"].append(f"Deleted memory {memory.id}")
        
        # Detect corrections
        correction = MemoryService.detect_correction(user_message, assistant_response)
        if correction["is_correction"]:
            # Handle as high-priority memory update
            new_memory = MemoryService.handle_conflict(
                db=db,
                user_id=user_id,
                new_content=correction["correction_content"]
            )
            results["corrections_handled"].append(new_memory.id)
        
        # Detect preferences
        preference = MemoryService.detect_preference(user_message)
        if preference["is_preference"]:
            memory = MemoryService.create_memory(
                db=db,
                user_id=user_id,
                content=preference["preference_content"],
                category=MemoryCategory.PREFERENCE,
                source=MemorySource.USER_EXPLICIT,
                importance=MemoryImportance.HIGH,
                confidence=0.85
            )
            results["memories_created"].append(memory.id)
        
        db.commit()
        return results