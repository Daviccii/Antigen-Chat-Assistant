"""Memory Service - Phase 3 Memory Intelligence System.

This service provides enhanced memory operations including:
- Memory categorization (user_profile, explicit, project, preference, conversational, correction)
- Importance levels (LOW, NORMAL, HIGH, CRITICAL)
- Confidence scoring (0.0 to 1.0)
- Source tracking (USER_EXPLICIT, USER_CORRECTION, CONVERSATION, SYSTEM, IMPORTED, INFERRED)
- Status management (ACTIVE, ARCHIVED, SUPERSEDED)
- Project association
- Memory deduplication
- Conflict resolution
- Enhanced retrieval pipeline
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
import json
import re

from .models import Memory, Project, User
from .time_service import TimeService


# Memory categories
class MemoryCategory:
    USER_PROFILE = "user_profile"
    EXPLICIT = "explicit"
    PROJECT = "project"
    PREFERENCE = "preference"
    CONVERSATIONAL = "conversational"
    CORRECTION = "correction"


# Memory importance levels
class MemoryImportance:
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Memory sources
class MemorySource:
    USER_EXPLICIT = "USER_EXPLICIT"
    USER_CORRECTION = "USER_CORRECTION"
    CONVERSATION = "CONVERSATION"
    SYSTEM = "SYSTEM"
    IMPORTED = "IMPORTED"
    INFERRED = "INFERRED"


# Memory status
class MemoryStatus:
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    SUPERSEDED = "SUPERSEDED"


class MemoryService:
    """Enhanced memory service with Phase 3 intelligence."""
    
    @staticmethod
    def create_memory(
        db: Session,
        user_id: int,
        content: str,
        memory_type: str = "fact",
        category: str = MemoryCategory.EXPLICIT,
        source: str = MemorySource.USER_EXPLICIT,
        importance: str = MemoryImportance.NORMAL,
        confidence: float = 0.8,
        project_id: Optional[int] = None,
        key: Optional[str] = None,
        tags: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """Create a new memory with enhanced metadata."""
        memory = Memory(
            user_id=user_id,
            type=memory_type,
            category=category,
            content=content,
            source=source,
            importance=importance,
            confidence=confidence,
            status=MemoryStatus.ACTIVE,
            project_id=project_id,
            key=key,
            tags=tags,
            extra_metadata=json.dumps(extra_metadata) if extra_metadata else None,
            last_confirmed_at=datetime.utcnow()
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory
    
    @staticmethod
    def detect_memory_command(user_message: str) -> Dict[str, Any]:
        """Detect if user message is a memory command."""
        message_lower = user_message.lower().strip()
        
        # Explicit memory commands
        remember_patterns = [
            r'^remember\s+(that\s+)?(.+)$',
            r'^don\'t\s+forget\s+(that\s+)?(.+)$',
            r'^keep\s+in\s+mind\s+(that\s+)?(.+)$',
            r'^from\s+now\s+on\s*,?\s*(.+)$',
            r'^note\s+(that\s+)?(.+)$',
        ]
        
        for pattern in remember_patterns:
            match = re.match(pattern, message_lower)
            if match:
                content = match.group(2) if match.groups() else match.group(1)
                return {
                    "is_command": True,
                    "command_type": "remember",
                    "content": content.strip(),
                    "original": user_message
                }
        
        # Forget commands
        forget_patterns = [
            r'^forget\s+(that\s+)?(.+)$',
            r'^remove\s+(that\s+)?(.+)$',
            r'^delete\s+(that\s+)?(.+)$',
        ]
        
        for pattern in forget_patterns:
            match = re.match(pattern, message_lower)
            if match:
                content = match.group(2) if match.groups() else match.group(1)
                return {
                    "is_command": True,
                    "command_type": "forget",
                    "content": content.strip(),
                    "original": user_message
                }
        
        # Query memory commands
        query_patterns = [
            r'^what\s+(do\s+you\s+)?remember\s+(about\s+)?(.+)$',
            r'^what\s+do\s+you\s+know\s+(about\s+)?(.+)$',
            r'^tell\s+me\s+(about\s+)?(.+)$',
        ]
        
        for pattern in query_patterns:
            match = re.match(pattern, message_lower)
            if match:
                content = match.group(2) if match.groups() else match.group(1)
                return {
                    "is_command": True,
                    "command_type": "query",
                    "content": content.strip(),
                    "original": user_message
                }
        
        return {"is_command": False}
    
    @staticmethod
    def detect_correction(user_message: str, previous_assistant_response: str) -> Dict[str, Any]:
        """Detect if user message is a correction."""
        message_lower = user_message.lower().strip()
        
        correction_patterns = [
            r'^no\s*,?\s*(.+)$',
            r'^that\'?s?\s+wrong\s*\.?\s*(.+)?$',
            r'^incorrect\s*\.?\s*(.+)?$',
            r'^actually\s*,?\s*(.+)$',
            r'^wait\s*,?\s*(.+)$',
        ]
        
        for pattern in correction_patterns:
            match = re.match(pattern, message_lower)
            if match:
                return {
                    "is_correction": True,
                    "correction_content": match.group(1).strip() if match.group(1) else "",
                    "original": user_message
                }
        
        return {"is_correction": False}
    
    @staticmethod
    def detect_preference(user_message: str) -> Dict[str, Any]:
        """Detect if user message expresses a preference."""
        message_lower = user_message.lower().strip()
        
        preference_patterns = [
            r'^i\s+prefer\s+(.+)$',
            r'^i\s+like\s+(.+)$',
            r'^i\s+don\'t\s+like\s+(.+)$',
            r'^always\s+(.+)$',
            r'^never\s+(.+)$',
            r'^from\s+now\s+on\s*,?\s*(.+)$',
        ]
        
        for pattern in preference_patterns:
            match = re.match(pattern, message_lower)
            if match:
                return {
                    "is_preference": True,
                    "preference_content": match.group(1).strip(),
                    "original": user_message
                }
        
        return {"is_preference": False}
    
    @staticmethod
    def find_similar_memories(
        db: Session,
        user_id: int,
        content: str,
        threshold: float = 0.8,
        limit: int = 5
    ) -> List[Memory]:
        """Find semantically similar memories for deduplication."""
        # Simple text-based similarity as fallback when pgvector is not available
        all_memories = db.query(Memory).filter(
            and_(
                Memory.user_id == user_id,
                Memory.status == MemoryStatus.ACTIVE
            )
        ).all()
        
        similar_memories = []
        content_words = set(content.lower().split())
        
        for memory in all_memories:
            memory_words = set(memory.content.lower().split())
            
            # Calculate Jaccard similarity
            intersection = content_words & memory_words
            union = content_words | memory_words
            similarity = len(intersection) / len(union) if union else 0
            
            if similarity >= threshold:
                similar_memories.append((memory, similarity))
        
        # Sort by similarity and return top results
        similar_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, _ in similar_memories[:limit]]
    
    @staticmethod
    def deduplicate_memory(
        db: Session,
        user_id: int,
        content: str,
        category: str = MemoryCategory.EXPLICIT
    ) -> Optional[Memory]:
        """Check for duplicate memories and return existing if found."""
        similar_memories = MemoryService.find_similar_memories(db, user_id, content, threshold=0.9, limit=1)
        
        for memory in similar_memories:
            # If same category and very similar content, consider it a duplicate
            if memory.category == category:
                # Update the existing memory instead of creating new one
                memory.last_confirmed_at = datetime.utcnow()
                memory.confidence = min(memory.confidence + 0.1, 1.0)  # Boost confidence
                db.commit()
                db.refresh(memory)
                return memory
        
        return None
    
    @staticmethod
    def handle_conflict(
        db: Session,
        user_id: int,
        new_content: str,
        conflict_key: Optional[str] = None
    ) -> Memory:
        """Handle conflicting memories by superseding old ones."""
        # Find conflicting memories
        query = db.query(Memory).filter(
            and_(
                Memory.user_id == user_id,
                Memory.status == MemoryStatus.ACTIVE
            )
        )
        
        if conflict_key:
            query = query.filter(Memory.key == conflict_key)
        else:
            # Find similar memories
            similar = MemoryService.find_similar_memories(db, user_id, new_content, threshold=0.7, limit=5)
            if similar:
                # Mark similar memories as superseded
                for memory in similar:
                    memory.status = MemoryStatus.SUPERSEDED
                    memory.extra_metadata = json.dumps({
                        "superseded_by": new_content,
                        "superseded_at": datetime.utcnow().isoformat()
                    })
        
        db.commit()
        
        # Create new memory with higher confidence
        new_memory = MemoryService.create_memory(
            db=db,
            user_id=user_id,
            content=new_content,
            category=MemoryCategory.CORRECTION,
            source=MemorySource.USER_CORRECTION,
            importance=MemoryImportance.HIGH,
            confidence=0.95,
            key=conflict_key
        )
        
        return new_memory
    
    @staticmethod
    def retrieve_relevant_memories(
        db: Session,
        user_id: int,
        query_text: str,
        project_id: Optional[int] = None,
        limit: int = 10,
        min_importance: str = MemoryImportance.NORMAL
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories using enhanced ranking."""
        # Build base query
        query = db.query(Memory).filter(
            and_(
                Memory.user_id == user_id,
                Memory.status == MemoryStatus.ACTIVE
            )
        )
        
        # Filter by project if specified
        if project_id:
            query = query.filter(Memory.project_id == project_id)
        
        # Filter by importance
        importance_order = {
            MemoryImportance.CRITICAL: 4,
            MemoryImportance.HIGH: 3,
            MemoryImportance.NORMAL: 2,
            MemoryImportance.LOW: 1
        }
        min_importance_value = importance_order.get(min_importance, 2)
        
        memories = query.all()
        
        # Score and rank memories
        scored_memories = []
        query_words = set(query_text.lower().split())
        
        for memory in memories:
            # Base score from importance
            importance_score = importance_order.get(memory.importance, 2)
            
            # Semantic similarity score (simple text-based)
            memory_words = set(memory.content.lower().split())
            intersection = query_words & memory_words
            union = query_words | memory_words
            semantic_score = len(intersection) / len(union) if union else 0
            
            # Confidence score
            confidence_score = memory.confidence or 0.5
            
            # Recency score (more recent = higher)
            days_since_access = 0
            if memory.last_accessed_at:
                days_since_access = (datetime.utcnow() - memory.last_accessed_at).days
            recency_score = max(0, 1 - days_since_access / 365)  # Decay over a year
            
            # Source priority
            source_priority = {
                MemorySource.USER_EXPLICIT: 1.0,
                MemorySource.USER_CORRECTION: 1.0,
                MemorySource.SYSTEM: 0.8,
                MemorySource.IMPORTED: 0.7,
                MemorySource.CONVERSATION: 0.6,
                MemorySource.INFERRED: 0.4
            }
            source_score = source_priority.get(memory.source, 0.5)
            
            # Category priority
            category_priority = {
                MemoryCategory.USER_PROFILE: 1.0,
                MemoryCategory.EXPLICIT: 1.0,
                MemoryCategory.CORRECTION: 1.0,
                MemoryCategory.PROJECT: 0.9,
                MemoryCategory.PREFERENCE: 0.8,
                MemoryCategory.CONVERSATIONAL: 0.6
            }
            category_score = category_priority.get(memory.category, 0.5)
            
            # Combined score
            total_score = (
                (importance_score * 0.3) +
                (semantic_score * 0.25) +
                (confidence_score * 0.2) +
                (recency_score * 0.1) +
                (source_score * 0.1) +
                (category_score * 0.05)
            )
            
            scored_memories.append({
                "memory": memory,
                "score": total_score,
                "importance_score": importance_score,
                "semantic_score": semantic_score,
                "confidence_score": confidence_score,
                "recency_score": recency_score
            })
        
        # Sort by total score and return top results
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        
        # Update last_accessed_at for retrieved memories
        for item in scored_memories[:limit]:
            item["memory"].last_accessed_at = datetime.utcnow()
        
        db.commit()
        
        # Return formatted results
        return [
            {
                "id": item["memory"].id,
                "content": item["memory"].content,
                "category": item["memory"].category,
                "importance": item["memory"].importance,
                "confidence": item["memory"].confidence,
                "source": item["memory"].source,
                "score": item["score"],
                "project_id": item["memory"].project_id
            }
            for item in scored_memories[:limit]
        ]
    
    @staticmethod
    def create_project(
        db: Session,
        user_id: int,
        name: str,
        description: Optional[str] = None
    ) -> Project:
        """Create a new project."""
        project = Project(
            user_id=user_id,
            name=name,
            description=description
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    
    @staticmethod
    def get_user_projects(db: Session, user_id: int) -> List[Project]:
        """Get all projects for a user."""
        return db.query(Project).filter(Project.user_id == user_id).all()
    
    @staticmethod
    def get_project_by_name(db: Session, user_id: int, name: str) -> Optional[Project]:
        """Get a project by name for a user."""
        return db.query(Project).filter(
            and_(Project.user_id == user_id, Project.name == name)
        ).first()
    
    @staticmethod
    def update_memory(
        db: Session,
        memory_id: int,
        user_id: int,
        **updates
    ) -> Optional[Memory]:
        """Update a memory with validation."""
        memory = db.query(Memory).filter(
            and_(Memory.id == memory_id, Memory.user_id == user_id)
        ).first()
        
        if not memory:
            return None
        
        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)
        
        memory.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(memory)
        return memory
    
    @staticmethod
    def delete_memory(db: Session, memory_id: int, user_id: int) -> bool:
        """Delete a memory with user validation."""
        memory = db.query(Memory).filter(
            and_(Memory.id == memory_id, Memory.user_id == user_id)
        ).first()
        
        if not memory:
            return False
        
        db.delete(memory)
        db.commit()
        return True
    
    @staticmethod
    def get_user_memories(
        db: Session,
        user_id: int,
        category: Optional[str] = None,
        project_id: Optional[int] = None,
        status: str = MemoryStatus.ACTIVE,
        limit: int = 100
    ) -> List[Memory]:
        """Get memories for a user with optional filters."""
        query = db.query(Memory).filter(Memory.user_id == user_id)
        
        if category:
            query = query.filter(Memory.category == category)
        if project_id:
            query = query.filter(Memory.project_id == project_id)
        if status:
            query = query.filter(Memory.status == status)
        
        return query.order_by(Memory.created_at.desc()).limit(limit).all()
