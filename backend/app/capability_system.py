"""Capability System - Foundational Architecture for Task Completion.

This module provides the foundational architecture for Antigen's capability system:
- Tool abstraction and registry
- Skill abstraction and registry  
- Task model and orchestration interface
- Permission system
- Execution and result handling

This is Phase A - the foundation that enables future capabilities to be added
without modifying the core orchestrator.
"""
from typing import Dict, Any, Optional, List, Callable, Protocol
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission System
# ---------------------------------------------------------------------------

class PermissionLevel(str, Enum):
    """Permission levels for tool execution."""
    READ_ONLY = "READ_ONLY"
    SAFE_ACTION = "SAFE_ACTION"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    RESTRICTED = "RESTRICTED"


# ---------------------------------------------------------------------------
# Tool System
# ---------------------------------------------------------------------------

@dataclass
class ToolInputSchema:
    """Schema for tool input validation."""
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolOutputSchema:
    """Schema for tool output validation."""
    type: str
    description: str


@dataclass
class Tool:
    """Represents a tool that can be used to perform actions."""
    name: str
    description: str
    input_schema: Dict[str, ToolInputSchema]
    output_schema: ToolOutputSchema
    permission_level: PermissionLevel = PermissionLevel.SAFE_ACTION
    domain: Optional[str] = None
    category: Optional[str] = None
    execution_handler: Optional[Callable] = None
    
    def can_execute(self, user_permission_level: PermissionLevel) -> bool:
        """Check if tool can be executed given user permission level."""
        permission_hierarchy = {
            PermissionLevel.READ_ONLY: 0,
            PermissionLevel.SAFE_ACTION: 1,
            PermissionLevel.REQUIRES_CONFIRMATION: 2,
            PermissionLevel.RESTRICTED: 3
        }
        return permission_hierarchy.get(user_permission_level, 0) >= permission_hierarchy.get(self.permission_level, 0)


class ToolRegistry:
    """Central registry for all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a new tool."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self, domain: Optional[str] = None, permission_level: Optional[PermissionLevel] = None) -> List[Tool]:
        """List available tools, optionally filtered by domain or permission level."""
        tools = list(self._tools.values())
        
        if domain:
            tools = [t for t in tools if t.domain == domain]
        
        if permission_level:
            tools = [t for t in tools if t.permission_level == permission_level]
        
        return tools
    
    def get_by_domain(self, domain: str) -> List[Tool]:
        """Get all tools for a specific domain."""
        return [t for t in self._tools.values() if t.domain == domain]


# Global tool registry instance
tool_registry = ToolRegistry()


# ---------------------------------------------------------------------------
# Skill System  
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """Represents a capability that can accomplish specific types of tasks."""
    name: str
    description: str
    domain: str
    required_tools: List[str]
    capabilities: List[str]
    instructions: str
    execution_strategy: str = "sequential"  # sequential, parallel, adaptive
    permission_level: PermissionLevel = PermissionLevel.SAFE_ACTION
    
    def get_required_tools(self, tool_registry: ToolRegistry) -> List[Tool]:
        """Get the actual Tool objects for this skill."""
        tools = []
        for tool_name in self.required_tools:
            tool = tool_registry.get(tool_name)
            if tool:
                tools.append(tool)
            else:
                logger.warning(f"Tool '{tool_name}' required by skill '{self.name}' not found")
        return tools


class SkillRegistry:
    """Central registry for all available skills."""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        """Register a new skill."""
        if skill.name in self._skills:
            logger.warning(f"Skill '{skill.name}' already registered, overwriting")
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def list_skills(self, domain: Optional[str] = None) -> List[Skill]:
        """List available skills, optionally filtered by domain."""
        skills = list(self._skills.values())
        
        if domain:
            skills = [s for s in skills if s.domain == domain]
        
        return skills
    
    def get_by_domain(self, domain: str) -> List[Skill]:
        """Get all skills for a specific domain."""
        return [s for s in self._skills.values() if s.domain == domain]
    
    def find_skill_for_task(self, task_description: str, domain: Optional[str] = None) -> Optional[Skill]:
        """Find a skill that might handle a given task (simple keyword matching for now)."""
        # This is a simple implementation - future versions could use semantic search
        task_lower = task_description.lower()
        
        candidates = self.list_skills(domain)
        
        for skill in candidates:
            # Check if task description matches skill capabilities or description
            for capability in skill.capabilities:
                if capability.lower() in task_lower or task_lower in capability.lower():
                    return skill
            
            if skill.description.lower() in task_lower or task_lower in skill.description.lower():
                return skill
        
        return None


# Global skill registry instance
skill_registry = SkillRegistry()


# ---------------------------------------------------------------------------
# Task System
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskStep:
    """A single step in a task execution plan."""
    step_id: str
    description: str
    tool_name: str
    input_data: Dict[str, Any]
    permission_level: PermissionLevel = PermissionLevel.SAFE_ACTION
    completed: bool = False
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class TaskPlan:
    """Execution plan for a task."""
    task_id: str
    description: str
    domain: str
    skill_name: str
    steps: List[TaskStep] = field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high
    requires_confirmation: bool = False
    
    def add_step(self, step: TaskStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)
    
    def get_pending_steps(self) -> List[TaskStep]:
        """Get steps that haven't been completed yet."""
        return [step for step in self.steps if not step.completed]


@dataclass
class Task:
    """Represents a task to be completed."""
    task_id: str
    description: str
    domain: str
    status: TaskStatus = TaskStatus.PENDING
    plan: Optional[TaskPlan] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: TaskStatus) -> None:
        """Update task status and timestamps."""
        self.status = status
        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.completed_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Execution and Result System
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of a tool execution."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskOrchestrator:
    """Orchestrates task execution using registered skills and tools."""
    
    def __init__(self, tool_registry: ToolRegistry, skill_registry: SkillRegistry):
        self.tool_registry = tool_registry
        self.skill_registry = skill_registry
    
    def analyze_task(self, task_description: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a task and determine appropriate skill and tools."""
        # Find appropriate skill
        skill = self.skill_registry.find_skill_for_task(task_description, domain)
        
        if not skill:
            return {
                "can_handle": False,
                "reason": "No appropriate skill found for this task",
                "suggested_domain": None
            }
        
        # Get required tools
        required_tools = skill.get_required_tools(self.tool_registry)
        
        return {
            "can_handle": True,
            "skill": skill.name,
            "domain": skill.domain,
            "required_tools": [tool.name for tool in required_tools],
            "permission_level": skill.permission_level.value,
            "estimated_complexity": "medium"  # Could be made more sophisticated
        }
    
    def create_task_plan(self, task: Task, skill: Skill) -> TaskPlan:
        """Create an execution plan for a task using a skill."""
        plan = TaskPlan(
            task_id=task.task_id,
            description=task.description,
            domain=task.domain,
            skill_name=skill.name
        )
        
        # For now, create a simple single-step plan
        # Future versions could use LLM to generate multi-step plans
        step = TaskStep(
            step_id=f"{task.task_id}_step_1",
            description=f"Execute {skill.name} for: {task.description}",
            tool_name=skill.required_tools[0] if skill.required_tools else "generic",
            input_data={"task_description": task.description},
            permission_level=skill.permission_level
        )
        plan.add_step(step)
        
        return plan
    
    def execute_step(self, step: TaskStep) -> ExecutionResult:
        """Execute a single task step."""
        tool = self.tool_registry.get(step.tool_name)
        
        if not tool:
            return ExecutionResult(
                success=False,
                error=f"Tool '{step.tool_name}' not found"
            )
        
        if not tool.execution_handler:
            return ExecutionResult(
                success=False,
                error=f"Tool '{step.tool_name}' has no execution handler"
            )
        
        try:
            import time
            start_time = time.time()
            
            # Execute the tool
            result_data = tool.execution_handler(step.input_data)
            
            execution_time = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                success=True,
                data=result_data,
                execution_time_ms=execution_time
            )
        except Exception as e:
            logger.exception(f"Error executing step {step.step_id}")
            return ExecutionResult(
                success=False,
                error=str(e)
            )
    
    def execute_task(self, task: Task) -> ExecutionResult:
        """Execute a task following its plan."""
        if not task.plan:
            return ExecutionResult(
                success=False,
                error="Task has no execution plan"
            )
        
        task.update_status(TaskStatus.IN_PROGRESS)
        
        try:
            for step in task.plan.get_pending_steps():
                # Check if confirmation is required
                if step.permission_level == PermissionLevel.REQUIRES_CONFIRMATION:
                    task.update_status(TaskStatus.WAITING_CONFIRMATION)
                    # In a real implementation, this would wait for user confirmation
                    # For now, we'll proceed with a warning
                    logger.warning(f"Step {step.step_id} requires confirmation, proceeding automatically")
                
                result = self.execute_step(step)
                
                if result.success:
                    step.completed = True
                    step.result = result.data
                else:
                    step.error = result.error
                    task.update_status(TaskStatus.FAILED)
                    task.error = f"Step {step.step_id} failed: {result.error}"
                    return result
            
            task.update_status(TaskStatus.COMPLETED)
            return ExecutionResult(
                success=True,
                data={"message": "Task completed successfully", "steps_completed": len(task.plan.steps)}
            )
        
        except Exception as e:
            logger.exception(f"Error executing task {task.task_id}")
            task.update_status(TaskStatus.FAILED)
            task.error = str(e)
            return ExecutionResult(
                success=False,
                error=str(e)
            )


# Global task orchestrator instance
task_orchestrator = TaskOrchestrator(tool_registry, skill_registry)


# ---------------------------------------------------------------------------
# Integration with Existing Systems
# ---------------------------------------------------------------------------

def integrate_with_context_engine(db, user, query_text: str = None, conversation_id: int = None) -> Dict[str, Any]:
    """Integration with existing ContextEngine.
    
    Provides task-relevant context like user preferences, project context, 
    and relevant memories to help with task planning and execution.
    """
    try:
        from .context_engine import ContextEngine
        
        context = ContextEngine.build_full_context(
            db=db,
            user=user,
            query_text=query_text,
            conversation_id=conversation_id
        )
        
        return context
    except Exception as e:
        logger.exception("Error integrating with context engine")
        return {}


def integrate_with_memory_service(db, user_id: int, task_result: Dict[str, Any], task_description: str) -> None:
    """Integration with existing MemoryService.
    
    Stores successful task execution results as memories for future reference.
    """
    try:
        from .memory_service import MemoryService, MemoryCategory, MemorySource, MemoryImportance
        
        # Only store successful, non-trivial results
        if task_result.get("success") and task_result.get("data"):
            # Create a memory about the successful task execution
            memory_content = f"Successfully completed task: {task_description}. Result: {str(task_result.get('data'))[:200]}"
            
            MemoryService.create_memory(
                db=db,
                user_id=user_id,
                content=memory_content,
                memory_type="task_result",
                category=MemoryCategory.CONVERSATIONAL,
                source=MemorySource.SYSTEM,
                importance=MemoryImportance.LOW,
                confidence=0.7
            )
            
            logger.info(f"Stored task result as memory for user {user_id}")
    except Exception as e:
        logger.exception("Error integrating with memory service")
        # Don't fail the task if memory storage fails


# ---------------------------------------------------------------------------
# Configuration and Extension
# ---------------------------------------------------------------------------

class CapabilityConfig:
    """Configuration for capability system."""
    
    def __init__(self):
        self.enabled_domains: List[str] = []
        self.default_permission_level: PermissionLevel = PermissionLevel.SAFE_ACTION
        self.max_execution_time_ms: float = 30000  # 30 seconds
        self.enable_autonomous_execution: bool = False
    
    def enable_domain(self, domain: str) -> None:
        """Enable a specific domain."""
        if domain not in self.enabled_domains:
            self.enabled_domains.append(domain)
    
    def is_domain_enabled(self, domain: str) -> bool:
        """Check if a domain is enabled."""
        return domain in self.enabled_domains


# Global capability configuration
capability_config = CapabilityConfig()