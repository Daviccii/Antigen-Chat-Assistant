"""LangGraph Orchestrator for Antigen Task Orchestration.

This module provides the main LangGraph workflow orchestration for Antigen.
It serves as an orchestration layer over the existing capability system.

Phase B1: Minimal graph with initialize_task node only.
Phase B2: Extended graph with LLM-powered planning nodes (understand, domain, skill, plan).
Phase B3: Extended graph with tool selection and permission validation nodes.
Phase B4: Extended graph with execution and result collection nodes.
Phase B5: Extended graph with verification, failure analysis, and recovery nodes.
Phase B6: Extended graph with memory integration node.
"""
from typing import Dict, Any, Optional
import logging
from langgraph.graph import StateGraph, END

from .langgraph_state import (
    AntigenTaskState, 
    TaskStatus, 
    create_initial_state
)
from .langgraph_nodes import (
    initialize_task,
    understand_task,
    identify_domain,
    select_skill,
    create_execution_plan,
    select_tools,
    validate_permissions,
    execute_plan,
    collect_results
)

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """Main orchestrator for LangGraph-based task execution.
    
    This class provides a clean interface for running tasks through LangGraph
    while integrating with the existing capability system.
    
    Phase B4: Extended graph with B3 tool/permission validation and B4 execution nodes.
    """
    
    def __init__(self):
        """Initialize the LangGraph orchestrator with the B4 complete workflow."""
        self.graph = self._build_graph()
        logger.info("LangGraph orchestrator initialized with B4 complete workflow")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Phase B4: Complete workflow with planning, tool selection, permission validation, and execution.
        Workflow: START -> initialize_task -> understand_task -> identify_domain 
                 -> select_skill -> create_execution_plan -> select_tools 
                 -> validate_permissions -> execute_plan -> collect_results -> END
        Later phases will add verification, recovery, and memory integration.
        
        Returns:
            Compiled LangGraph StateGraph
        """
        # Create the graph with our state type
        workflow = StateGraph(AntigenTaskState)
        
        # Add Phase B1 node
        workflow.add_node("initialize_task", initialize_task)
        
        # Add Phase B2 planning nodes
        workflow.add_node("understand_task", understand_task)
        workflow.add_node("identify_domain", identify_domain)
        workflow.add_node("select_skill", select_skill)
        workflow.add_node("create_execution_plan", create_execution_plan)
        
        # Add Phase B3 tool selection and permission validation nodes
        workflow.add_node("select_tools", select_tools)
        workflow.add_node("validate_permissions", validate_permissions)
        
        # Add Phase B4 execution and result collection nodes
        workflow.add_node("execute_plan", execute_plan)
        workflow.add_node("collect_results", collect_results)
        
        # Define the Phase B4 workflow
        workflow.set_entry_point("initialize_task")
        workflow.add_edge("initialize_task", "understand_task")
        workflow.add_edge("understand_task", "identify_domain")
        workflow.add_edge("identify_domain", "select_skill")
        workflow.add_edge("select_skill", "create_execution_plan")
        workflow.add_edge("create_execution_plan", "select_tools")
        workflow.add_edge("select_tools", "validate_permissions")
        workflow.add_edge("validate_permissions", "execute_plan")
        workflow.add_edge("execute_plan", "collect_results")
        workflow.add_edge("collect_results", END)
        
        # Compile the graph
        return workflow.compile()
    
    async def run_task(
        self,
        user_request: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a task through the LangGraph orchestration.
        
        Phase B4: Complete execution with planning, tool selection, permission validation, and execution.
        
        Args:
            user_request: The user's natural language request
            user_id: The ID of the user making the request
            conversation_id: Optional conversation ID for context
            context: Optional context from ContextEngine
        
        Returns:
            Dictionary containing the final state and execution results
        """
        logger.info(f"Starting LangGraph task execution for user {user_id}")
        
        # Create initial state
        initial_state = create_initial_state(
            user_request=user_request,
            user_id=user_id,
            conversation_id=conversation_id,
            context=context
        )
        
        try:
            # Run the graph (now async due to LLM calls)
            final_state = await self.graph.ainvoke(initial_state)
            
            # Prepare result with B3/B4 fields
            result = {
                "success": final_state["status"] != TaskStatus.FAILED,
                "status": final_state["status"].value,
                "user_request": final_state["user_request"],
                "user_id": final_state["user_id"],
                "conversation_id": final_state["conversation_id"],
                "selected_domain": final_state["selected_domain"],
                "selected_skill": final_state["selected_skill"],
                "plan": final_state["plan"],
                # B3 fields
                "selected_tools": final_state.get("selected_tools"),
                "tool_selection_results": final_state.get("tool_selection_results"),
                "unavailable_tools": final_state.get("unavailable_tools"),
                "tool_validation_errors": final_state.get("tool_validation_errors"),
                "permission_requirements": final_state.get("permission_requirements"),
                "permission_results": final_state.get("permission_results"),
                "blocked_operations": final_state.get("blocked_operations"),
                "confirmation_requirements": final_state.get("confirmation_requirements"),
                # B4 fields
                "execution_state": final_state.get("execution_state"),
                "step_execution_states": final_state.get("step_execution_states"),
                "execution_results": final_state["execution_results"],
                "errors": final_state["errors"],
                "final_result": final_state["final_result"],
                "metadata": final_state["metadata"],
                "created_at": final_state["created_at"].isoformat(),
                "updated_at": final_state["updated_at"].isoformat()
            }
            
            logger.info(f"LangGraph task execution completed with status: {final_state['status'].value}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in LangGraph task execution: {e}")
            return {
                "success": False,
                "status": TaskStatus.FAILED.value,
                "user_request": user_request,
                "user_id": user_id,
                "selected_domain": None,
                "selected_skill": None,
                "plan": None,
                # B3 fields
                "selected_tools": None,
                "tool_selection_results": None,
                "unavailable_tools": None,
                "tool_validation_errors": None,
                "permission_requirements": None,
                "permission_results": None,
                "blocked_operations": None,
                "confirmation_requirements": None,
                # B4 fields
                "execution_state": "error",
                "step_execution_states": None,
                "execution_results": [],
                "errors": [f"LangGraph execution error: {str(e)}"],
                "final_result": None,
                "metadata": {},
                "created_at": initial_state["created_at"].isoformat(),
                "updated_at": initial_state["updated_at"].isoformat()
            }
    
    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the current graph structure.
        
        Returns:
            Dictionary with graph metadata
        """
        return {
            "phase": "B4",
            "description": "LangGraph with complete B4 workflow: planning, tool selection, permission validation, and execution",
            "nodes": [
                "initialize_task",
                "understand_task",
                "identify_domain",
                "select_skill",
                "create_execution_plan",
                "select_tools",
                "validate_permissions",
                "execute_plan",
                "collect_results"
            ],
            "workflow": "START -> initialize_task -> understand_task -> identify_domain -> select_skill -> create_execution_plan -> select_tools -> validate_permissions -> execute_plan -> collect_results -> END",
            "future_phases": [
                "B5: Error recovery and verification",
                "B6: Memory integration and learning",
                "C: Advanced execution / parallel execution",
                "D+: Software engineering agent",
                "E+: Data analytics",
                "F+: Math/algorithms",
                "G+: IT/networking",
                "H+: Defensive cybersecurity",
                "I+: Finance/stock/Forex",
                "J+: Research",
                "K+: Document intelligence",
                "L+: Computer vision",
                "M+: Voice/multimodal",
                "N+: Automation",
                "O+: Learning/adaptation",
                "P+: Production hardening",
                "Q: Autonomous assistant integration"
            ]
        }


# Global orchestrator instance
langgraph_orchestrator = LangGraphOrchestrator()