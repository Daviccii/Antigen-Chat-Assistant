"""API Routes for Capability System.

This module provides FastAPI endpoints for interacting with the capability system:
- List available tools and skills
- Analyze tasks and create execution plans
- Execute tasks
- Check system status
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import uuid

from .capability_system import (
    tool_registry, skill_registry, task_orchestrator,
    Task, TaskStatus, PermissionLevel, capability_config,
    integrate_with_context_engine, integrate_with_memory_service
)
from .gated_execution import execute_tool_gated
from .auth import get_current_active_user
from .models import User
from .db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class TaskAnalysisRequest(BaseModel):
    description: str
    domain: Optional[str] = None


class TaskExecutionRequest(BaseModel):
    description: str
    domain: Optional[str] = None
    auto_execute: bool = False


class ToolInfo(BaseModel):
    name: str
    description: str
    permission_level: str
    domain: Optional[str] = None
    category: Optional[str] = None


class SkillInfo(BaseModel):
    name: str
    description: str
    domain: str
    required_tools: List[str]
    capabilities: List[str]
    permission_level: str


class TaskInfo(BaseModel):
    task_id: str
    description: str
    domain: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Capability Status Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_capability_status(current_user: User = Depends(get_current_active_user)):
    """Get the current status of the capability system."""
    return {
        "status": "operational",
        "enabled_domains": capability_config.enabled_domains,
        "total_tools": len(tool_registry.list_tools()),
        "total_skills": len(skill_registry.list_skills()),
        "default_permission_level": capability_config.default_permission_level.value,
        "auto_execution_enabled": capability_config.enable_autonomous_execution
    }


@router.get("/tools")
async def list_tools(
    domain: Optional[str] = None,
    permission_level: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """List available tools, optionally filtered by domain or permission level."""
    tools = tool_registry.list_tools(domain=domain)
    
    if permission_level:
        try:
            perm_level = PermissionLevel(permission_level)
            tools = [t for t in tools if t.permission_level == perm_level]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid permission level: {permission_level}")
    
    return {
        "tools": [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                permission_level=tool.permission_level.value,
                domain=tool.domain,
                category=tool.category
            )
            for tool in tools
        ],
        "count": len(tools)
    }


@router.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str, current_user: User = Depends(get_current_active_user)):
    """Get detailed information about a specific tool."""
    tool = tool_registry.get(tool_name)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": {k: {"type": v.type, "description": v.description, "required": v.required} for k, v in tool.input_schema.items()},
        "output_schema": {"type": tool.output_schema.type, "description": tool.output_schema.description},
        "permission_level": tool.permission_level.value,
        "domain": tool.domain,
        "category": tool.category
    }


@router.get("/skills")
async def list_skills(
    domain: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """List available skills, optionally filtered by domain."""
    skills = skill_registry.list_skills(domain=domain)
    
    return {
        "skills": [
            SkillInfo(
                name=skill.name,
                description=skill.description,
                domain=skill.domain,
                required_tools=skill.required_tools,
                capabilities=skill.capabilities,
                permission_level=skill.permission_level.value
            )
            for skill in skills
        ],
        "count": len(skills)
    }


@router.get("/skills/{skill_name}")
async def get_skill_info(skill_name: str, current_user: User = Depends(get_current_active_user)):
    """Get detailed information about a specific skill."""
    skill = skill_registry.get(skill_name)
    
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    return {
        "name": skill.name,
        "description": skill.description,
        "domain": skill.domain,
        "required_tools": skill.required_tools,
        "capabilities": skill.capabilities,
        "instructions": skill.instructions,
        "execution_strategy": skill.execution_strategy,
        "permission_level": skill.permission_level.value
    }


@router.get("/domains")
async def list_domains(current_user: User = Depends(get_current_active_user)):
    """List all available domains."""
    domains = set()
    for tool in tool_registry.list_tools():
        if tool.domain:
            domains.add(tool.domain)
    
    for skill in skill_registry.list_skills():
        domains.add(skill.domain)
    
    return {
        "domains": sorted(list(domains)),
        "enabled_domains": capability_config.enabled_domains
    }


# ---------------------------------------------------------------------------
# Task Analysis and Planning Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_task(
    request: TaskAnalysisRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Analyze a task to determine if it can be handled and how."""
    try:
        analysis = task_orchestrator.analyze_task(request.description, request.domain)
        
        # Check if domain is enabled
        if analysis.get("domain") and not capability_config.is_domain_enabled(analysis["domain"]):
            analysis["can_handle"] = False
            analysis["reason"] = f"Domain '{analysis['domain']}' is not enabled"
        
        return analysis
    except Exception as e:
        logger.exception(f"Error analyzing task: {request.description}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Task Execution Endpoints
# ---------------------------------------------------------------------------

@router.post("/execute")
async def execute_task(
    request: TaskExecutionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute a task using the capability system."""
    db = SessionLocal()
    try:
        # Get context from existing ContextEngine
        context = integrate_with_context_engine(db, current_user, request.description)
        
        # First analyze the task
        analysis = task_orchestrator.analyze_task(request.description, request.domain)
        
        if not analysis["can_handle"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot handle this task: {analysis.get('reason', 'Unknown reason')}"
            )
        
        # Check domain is enabled
        if analysis.get("domain") and not capability_config.is_domain_enabled(analysis["domain"]):
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{analysis['domain']}' is not enabled"
            )
        
        # Check permission level
        perm_level = PermissionLevel(analysis.get("permission_level", "SAFE_ACTION"))
        if perm_level == PermissionLevel.RESTRICTED:
            raise HTTPException(
                status_code=403,
                detail="This task requires restricted permission level"
            )
        
        # Create task
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            description=request.description,
            domain=analysis.get("domain", "general")
        )
        
        # Get the skill
        skill = skill_registry.get(analysis["skill"])
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{analysis['skill']}' not found")
        
        # Create execution plan
        task.plan = task_orchestrator.create_task_plan(task, skill)
        
        # Check if auto-execution is enabled
        if not request.auto_execute and not capability_config.enable_autonomous_execution:
            # Return the plan without executing
            return {
                "task_id": task.task_id,
                "status": "planned",
                "description": task.description,
                "domain": task.domain,
                "context_provided": bool(context),
                "plan": {
                    "skill": task.plan.skill_name,
                    "steps": [
                        {
                            "step_id": step.step_id,
                            "description": step.description,
                            "tool": step.tool_name,
                            "permission_level": step.permission_level.value
                        }
                        for step in task.plan.steps
                    ]
                },
                "message": "Task planned but not executed. Set auto_execute=true to execute."
            }
        
        # Execute the task, routed through the Security Gateway — every
        # step's tool call goes through execute_tool_gated, bound to this
        # request's db session and user, rather than running ungated.
        def bound_executor(tool, input_data):
            return execute_tool_gated(db, current_user.id, tool, input_data)

        result = task_orchestrator.execute_task(task, executor=bound_executor)
        
        # Store successful results in memory
        if result.success:
            integrate_with_memory_service(db, current_user.id, {"success": True, "data": result.data}, request.description)
        
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "description": task.description,
            "domain": task.domain,
            "result": result.data if result.success else None,
            "error": result.error if not result.success else None,
            "execution_time_ms": result.execution_time_ms,
            "context_used": bool(context)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error executing task: {request.description}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Direct Tool Execution Endpoints (for testing and manual use)
# ---------------------------------------------------------------------------

@router.post("/tools/{tool_name}/execute")
async def execute_tool_directly(
    tool_name: str,
    input_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """Execute a tool directly with provided input data."""
    db = SessionLocal()
    try:
        tool = tool_registry.get(tool_name)
        
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        # Everything past this point — kill switch, category switch,
        # allowed-areas, RESTRICTED hard-block, audit logging — is
        # decided by the Security Gateway inside execute_tool_gated, not
        # here. This endpoint used to call tool.execution_handler
        # directly with only a coarse RESTRICTED check; that's gone now.
        result = execute_tool_gated(db, current_user.id, tool, input_data)

        if not result.success:
            status_code = 403 if "Blocked by Security Gateway" in (result.error or "") else 500
            if result.metadata.get("needs_confirmation"):
                status_code = 409
            raise HTTPException(status_code=status_code, detail=result.error)

        return {
            "tool": tool_name,
            "success": True,
            "result": result.data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()