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

from .models import User, Memory, Project
from .time_service import TimeService
from .memory_service import (
    MemoryService,
    MemoryCategory,
    MemoryImportance,
    MemorySource
)


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
        
        # 1. Time Context (Authoritative)
        time_context = TimeService.get_time_context(user.timezone or "Africa/Nairobi")
        
        # 2. User Profile Context
        user_profile = ContextEngine._build_user_profile(user)
        
        # 3. Memory Context
        memory_context = ContextEngine._build_memory_context(
            db, user.id, query_text, project_id
        )
        
        # 4. Project Context
        project_context = ContextEngine._build_project_context(db, user.id, project_id)
        
        # 5. Conversation Context
        conversation_context = ContextEngine._build_conversation_context(
            db, user.id, conversation_id
        )
        
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
        
        # Get user profile memories
        profile_memories = MemoryService.get_user_memories(
            db, user_id, category=MemoryCategory.USER_PROFILE, limit=5
        )
        
        # Get explicit memories
        explicit_memories = MemoryService.get_user_memories(
            db, user_id, category=MemoryCategory.EXPLICIT, limit=10
        )
        
        # Get preference memories
        preference_memories = MemoryService.get_user_memories(
            db, user_id, category=MemoryCategory.PREFERENCE, limit=5
        )
        
        # Get relevant memories based on query
        relevant_memories = []
        if query_text:
            relevant_memories = MemoryService.retrieve_relevant_memories(
                db, user_id, query_text, project_id=project_id, limit=8
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
        """Build project context."""
        projects = MemoryService.get_user_projects(db, user_id)
        
        project_details = []
        for project in projects:
            project_memories = MemoryService.get_user_memories(
                db, user_id, project_id=project.id, limit=10
            )
            
            project_details.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "memory_count": len(project_memories),
                "key_memories": [
                    {
                        "content": m.content,
                        "importance": m.importance
                    }
                    for m in project_memories[:5]  # Top 5 memories per project
                ]
            })
        
        # If specific project requested, prioritize it
        if project_id:
            specific_project = next(
                (p for p in project_details if p["id"] == project_id),
                None
            )
            if specific_project:
                return {
                    "current_project": specific_project,
                    "all_projects": project_details
                }
        
        return {
            "all_projects": project_details
        }
    
    @staticmethod
    def _build_conversation_context(
        db: Session,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build conversation context."""
        from .models import Conversation, Message as MessageModel
        
        if not conversation_id:
            return {"has_active_conversation": False}
        
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            return {"has_active_conversation": False}
        
        messages = (
            db.query(MessageModel)
            .filter(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at.asc())
            .all()
        )
        
        # Get recent messages (last 10)
        recent_messages = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.created_at.isoformat()
            }
            for m in messages[-10:]
        ]
        
        # Generate conversation summary for long conversations
        summary = None
        if len(messages) > 20:
            summary = ContextEngine._generate_conversation_summary(messages)
        
        return {
            "has_active_conversation": True,
            "conversation_id": conversation.id,
            "message_count": len(messages),
            "recent_messages": recent_messages,
            "summary": summary
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