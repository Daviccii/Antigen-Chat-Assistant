"""LangGraph Orchestrator for Antigen Task Orchestration.

This module provides the main LangGraph workflow orchestration for Antigen.
It serves as an orchestration layer over the existing capability system.

Phase B1: Minimal graph with initialize_task node only.
Phase B2: Extended graph with LLM-powered planning nodes (understand, domain, skill, plan).
The graph will be extended in later phases with execution, verification, and recovery nodes.
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
    create_execution_plan
)

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """Main orchestrator for LangGraph-based task execution.
    
    This class provides a clean interface for running tasks through LangGraph
    while integrating with the existing capability system.
    
    Phase B2: Extended graph with LLM-powered planning nodes.
    """
    
    def __init__(self):
        """Initialize the LangGraph orchestrator with the B2 planning workflow."""
        self.graph = self._build_graph()
        logger.info("LangGraph orchestrator initialized with B2 planning workflow")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Phase B2: Extended workflow with LLM-powered planning.
        Workflow: START -> initialize_task -> understand_task -> identify_domain 
                 -> select_skill -> create_execution_plan -> END
        Later phases will add execution, verification, and recovery.
        
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
        
        # Define the Phase B2 workflow
        workflow.set_entry_point("initialize_task")
        workflow.add_edge("initialize_task", "understand_task")
        workflow.add_edge("understand_task", "identify_domain")
        workflow.add_edge("identify_domain", "select_skill")
        workflow.add_edge("select_skill", "create_execution_plan")
        workflow.add_edge("create_execution_plan", END)
        
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
        
        Phase B2: Execution with LLM-powered planning (understand, domain, skill, plan).
        Later phases will add execution, verification, and recovery.
        
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
            
            # Prepare result
            result = {
                "success": final_state["status"] != TaskStatus.FAILED,
                "status": final_state["status"].value,
                "user_request": final_state["user_request"],
                "user_id": final_state["user_id"],
                "conversation_id": final_state["conversation_id"],
                "selected_domain": final_state["selected_domain"],
                "selected_skill": final_state["selected_skill"],
                "plan": final_state["plan"],
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
                "errors": [f"LangGraph execution error: {str(e)}"],
                "execution_results": [],
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
            "phase": "B2",
            "description": "LangGraph with LLM-powered intelligent planning",
            "nodes": [
                "initialize_task",
                "understand_task",
                "identify_domain",
                "select_skill",
                "create_execution_plan"
            ],
            "workflow": "START -> initialize_task -> understand_task -> identify_domain -> select_skill -> create_execution_plan -> END",
            "future_phases": [
                "B3: Intelligent tool selection and permission validation",
                "B4: Sequential execution with existing capability system",
                "B5: Error recovery and verification",
                "B6: Memory integration and learning"
            ]
        }


# Global orchestrator instance
langgraph_orchestrator = LangGraphOrchestrator()