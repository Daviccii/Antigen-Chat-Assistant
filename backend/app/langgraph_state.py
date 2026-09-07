"""LangGraph State Management for Antigen Task Orchestration.

This module defines the state structure for LangGraph-based task orchestration.
The state is designed to integrate with the existing capability system while providing
extensible structure for future intelligent planning and execution.

Phase B1: Basic state structure only. Planning, execution, and recovery to be added in later phases.
Phase B3: Extended with tool selection and permission validation fields.
Phase B4: Extended with execution state and result collection fields.
"""
from typing import TypedDict, Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Status of a task in the LangGraph workflow."""
    PENDING = "PENDING"
    INITIALIZING = "INITIALIZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class AntigenTaskState(TypedDict):
    """State for Antigen task orchestration through LangGraph.
    
    This state integrates with the existing capability system while providing
    the structure needed for intelligent multi-step planning and execution.
    
    Phase B1: Basic structure only. Fields will be populated in later phases.
    Phase B3: Added tool selection and permission validation fields.
    Phase B4: Added execution state and result collection fields.
    """
    # Core request information
    user_request: str
    user_id: int
    conversation_id: Optional[int]
    
    # Context from existing systems
    context: Optional[Dict[str, Any]]
    
    # Capability system integration
    selected_domain: Optional[str]
    selected_skill: Optional[str]
    
    # Planning (Phase B2)
    plan: Optional[Dict[str, Any]]
    
    # Tool Selection (Phase B3)
    selected_tools: Optional[Dict[str, Any]]  # Maps step numbers to selected tools
    tool_selection_results: Optional[Dict[str, Any]]  # Detailed selection metadata
    unavailable_tools: List[str]  # Tools that were requested but not available
    tool_validation_errors: List[str]  # Errors during tool validation
    
    # Permission Validation (Phase B3)
    permission_requirements: Optional[Dict[str, Any]]  # Permission requirements per step
    permission_results: Optional[Dict[str, Any]]  # Permission validation results
    blocked_operations: List[str]  # Operations blocked by permissions
    confirmation_requirements: List[str]  # Operations requiring user confirmation
    
    # Execution tracking (Phase B4)
    current_step: Optional[int]
    execution_results: Optional[List[Dict[str, Any]]]
    execution_state: Optional[str]  # Overall execution state (pending, running, completed, failed, etc.)
    step_execution_states: Optional[Dict[str, str]]  # Individual step states
    
    # Error handling (to be implemented in Phase B5)
    errors: Optional[List[str]]
    
    # Verification (to be implemented in Phase B5)
    verification_result: Optional[Dict[str, Any]]
    
    # Final output
    final_result: Optional[Dict[str, Any]]
    
    # Workflow state
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    
    # Metadata for extensibility
    metadata: Dict[str, Any]


def create_initial_state(
    user_request: str,
    user_id: int,
    conversation_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> AntigenTaskState:
    """Create an initial task state for LangGraph orchestration.
    
    Args:
        user_request: The user's natural language request
        user_id: The ID of the user making the request
        conversation_id: Optional conversation ID for context
        context: Optional context from ContextEngine
    
    Returns:
        Initial AntigenTaskState with default values
    """
    now = datetime.utcnow()
    
    return AntigenTaskState(
        user_request=user_request,
        user_id=user_id,
        conversation_id=conversation_id,
        context=context,
        selected_domain=None,
        selected_skill=None,
        plan=None,
        # Phase B3 fields
        selected_tools=None,
        tool_selection_results=None,
        unavailable_tools=[],
        tool_validation_errors=[],
        permission_requirements=None,
        permission_results=None,
        blocked_operations=[],
        confirmation_requirements=[],
        # Phase B4 fields
        current_step=None,
        execution_results=[],
        execution_state="pending",
        step_execution_states=None,
        # Other fields
        errors=[],
        verification_result=None,
        final_result=None,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
        metadata={}
    )


def update_state_status(state: AntigenTaskState, new_status: TaskStatus) -> AntigenTaskState:
    """Update the status of a task state.
    
    Args:
        state: Current task state
        new_status: New status to set
    
    Returns:
        Updated task state
    """
    state["status"] = new_status
    state["updated_at"] = datetime.utcnow()
    return state


def add_execution_result(state: AntigenTaskState, result: Dict[str, Any]) -> AntigenTaskState:
    """Add an execution result to the state.
    
    Args:
        state: Current task state
        result: Execution result to add
    
    Returns:
        Updated task state
    """
    state["execution_results"].append(result)
    state["updated_at"] = datetime.utcnow()
    return state


def add_error(state: AntigenTaskState, error: str) -> AntigenTaskState:
    """Add an error to the state.
    
    Args:
        state: Current task state
        error: Error message to add
    
    Returns:
        Updated task state
    """
    state["errors"].append(error)
    state["updated_at"] = datetime.utcnow()
    return state