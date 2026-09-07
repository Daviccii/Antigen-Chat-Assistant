"""Tests for LangGraph Phase B1 Foundation.

Tests the basic LangGraph integration:
- State creation and management
- Node execution
- Graph construction and execution
- Integration with existing systems

Phase B1: Basic functionality tests only.
Note: Updated for B2 async interface compatibility. Tests now run through
the B2 workflow but verify B1 foundation functionality remains intact.
"""
import pytest
import sys
import os
import asyncio
from datetime import datetime

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.langgraph_state import (
    AntigenTaskState,
    TaskStatus,
    create_initial_state,
    update_state_status,
    add_execution_result,
    add_error
)
from app.langgraph_nodes import initialize_task
from app.langgraph_orchestrator import LangGraphOrchestrator, langgraph_orchestrator
from unittest.mock import patch


# Simple mock for B1 tests that now run through B2 workflow
async def simple_mock_llm(messages, temperature=0.7, max_tokens=1000):
    """Simple mock LLM for B1 tests."""
    last_message = messages[-1]["content"].lower()
    
    if "analyze the following user request" in last_message and "json format" in last_message:
        return '{"task_type": "test", "primary_objective": "test", "key_entities": [], "parameters": {}, "constraints": [], "expected_output": "test"}'
    elif "select the most appropriate domain" in last_message:
        return "software_engineering"
    elif "select the most appropriate skill" in last_message:
        return "analyze_project"
    elif "create a detailed execution plan" in last_message:
        return '{"steps": [{"step_number": 1, "description": "test", "tool": "test", "inputs": {}, "expected_output": "test"}], "estimated_complexity": "low", "requires_confirmation": false}'
    
    return "test"


# ---------------------------------------------------------------------------
# State Management Tests
# ---------------------------------------------------------------------------

def test_create_initial_state():
    """Test that initial state can be created with proper defaults."""
    state = create_initial_state(
        user_request="Test request",
        user_id=1,
        conversation_id=123,
        context={"test": "context"}
    )
    
    assert state["user_request"] == "Test request"
    assert state["user_id"] == 1
    assert state["conversation_id"] == 123
    assert state["context"] == {"test": "context"}
    assert state["status"] == TaskStatus.PENDING
    assert state["selected_domain"] is None
    assert state["selected_skill"] is None
    assert state["plan"] is None
    assert state["execution_results"] == []
    assert state["errors"] == []
    assert state["created_at"] is not None
    assert state["updated_at"] is not None
    assert state["metadata"] == {}


def test_create_initial_state_minimal():
    """Test that initial state can be created with minimal parameters."""
    state = create_initial_state(
        user_request="Minimal test",
        user_id=2
    )
    
    assert state["user_request"] == "Minimal test"
    assert state["user_id"] == 2
    assert state["conversation_id"] is None
    assert state["context"] is None
    assert state["status"] == TaskStatus.PENDING


def test_update_state_status():
    """Test that state status can be updated."""
    state = create_initial_state("Test", 1)
    original_updated_at = state["updated_at"]
    
    updated = update_state_status(state, TaskStatus.INITIALIZING)
    
    assert updated["status"] == TaskStatus.INITIALIZING
    assert updated["updated_at"] >= original_updated_at


def test_add_execution_result():
    """Test that execution results can be added to state."""
    state = create_initial_state("Test", 1)
    
    result = {"step": "test_step", "output": "success"}
    updated = add_execution_result(state, result)
    
    assert len(updated["execution_results"]) == 1
    assert updated["execution_results"][0] == result


def test_add_error():
    """Test that errors can be added to state."""
    state = create_initial_state("Test", 1)
    
    error_message = "Test error occurred"
    updated = add_error(state, error_message)
    
    assert len(updated["errors"]) == 1
    assert updated["errors"][0] == error_message


# ---------------------------------------------------------------------------
# Node Tests
# ---------------------------------------------------------------------------

def test_initialize_task_node():
    """Test that the initialize_task node works correctly."""
    state = create_initial_state("Test request", 1)
    
    updated_state = initialize_task(state)
    
    assert updated_state["status"] == TaskStatus.INITIALIZING
    assert updated_state["user_request"] == "Test request"
    assert updated_state["metadata"]["initialized"] == True
    assert "initialization_timestamp" in updated_state["metadata"]
    assert len(updated_state["errors"]) == 0


def test_initialize_task_node_with_whitespace():
    """Test that initialize_task normalizes user request."""
    state = create_initial_state("  Test request with spaces  ", 1)
    
    updated_state = initialize_task(state)
    
    assert updated_state["user_request"] == "Test request with spaces"


def test_initialize_task_node_missing_request():
    """Test that initialize_task handles missing user_request."""
    state = create_initial_state("", 1)
    state["user_request"] = ""  # Force empty
    
    updated_state = initialize_task(state)
    
    assert updated_state["status"] == TaskStatus.FAILED
    assert len(updated_state["errors"]) > 0
    assert "Missing user_request" in updated_state["errors"][0]


def test_initialize_task_node_missing_user_id():
    """Test that initialize_task handles missing user_id."""
    state = create_initial_state("Test", None)
    state["user_id"] = None  # Force None
    
    updated_state = initialize_task(state)
    
    assert updated_state["status"] == TaskStatus.FAILED
    assert len(updated_state["errors"]) > 0
    assert "Missing user_id" in updated_state["errors"][0]


# ---------------------------------------------------------------------------
# Orchestrator Tests
# ---------------------------------------------------------------------------

def test_orchestrator_initialization():
    """Test that the orchestrator can be initialized."""
    orchestrator = LangGraphOrchestrator()
    
    assert orchestrator is not None
    assert orchestrator.graph is not None


async def test_orchestrator_run_task_basic():
    """Test basic task execution through the orchestrator."""
    result = await langgraph_orchestrator.run_task(
        user_request="Test task",
        user_id=1
    )
    
    assert result["success"] == True
    # With B2 workflow, status will be PLANNING after full execution
    assert result["status"] in [TaskStatus.INITIALIZING.value, TaskStatus.PLANNING.value]
    assert result["user_request"] == "Test task"
    assert result["user_id"] == 1
    assert result["metadata"]["initialized"] == True


async def test_orchestrator_run_task_with_context():
    """Test task execution with context."""
    result = await langgraph_orchestrator.run_task(
        user_request="Test with context",
        user_id=1,
        conversation_id=123,
        context={"test": "context"}
    )
    
    assert result["success"] == True
    assert result["conversation_id"] == 123
    # Context is passed to the state but may not be returned in result dict
    # That's fine for B1 - the important part is it doesn't cause errors


def test_orchestrator_get_graph_info():
    """Test that graph information can be retrieved."""
    info = langgraph_orchestrator.get_graph_info()
    
    # Updated to expect B2 since orchestrator now uses B2 workflow
    assert info["phase"] == "B2"
    # Should still have B1 node plus B2 nodes
    assert "initialize_task" in info["nodes"]
    assert len(info["nodes"]) > 1  # Should have more nodes than just initialize_task
    assert len(info["future_phases"]) > 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

async def test_end_to_end_b1_workflow():
    """Test complete B1 workflow from state creation to graph execution."""
    # Create initial state
    state = create_initial_state(
        user_request="End-to-end test",
        user_id=1,
        conversation_id=456
    )
    
    # Verify initial state
    assert state["status"] == TaskStatus.PENDING
    
    # Run through orchestrator
    result = await langgraph_orchestrator.run_task(
        user_request="End-to-end test",
        user_id=1,
        conversation_id=456
    )
    
    # Verify final result
    assert result["success"] == True
    # With B2 workflow, status will be PLANNING after full execution
    assert result["status"] in [TaskStatus.INITIALIZING.value, TaskStatus.PLANNING.value]
    assert result["metadata"]["initialized"] == True
    assert len(result["errors"]) == 0


# ---------------------------------------------------------------------------
# Run Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running LangGraph B1 Foundation Tests...")
    
    # Initialize capability system for B2 workflow compatibility
    from app.capability_skills import initialize_basic_domains
    initialize_basic_domains()
    
    # State Management Tests
    test_create_initial_state()
    print("[PASS] create_initial_state test passed")
    
    test_create_initial_state_minimal()
    print("[PASS] create_initial_state minimal test passed")
    
    test_update_state_status()
    print("[PASS] update_state_status test passed")
    
    test_add_execution_result()
    print("[PASS] add_execution_result test passed")
    
    test_add_error()
    print("[PASS] add_error test passed")
    
    # Node Tests
    test_initialize_task_node()
    print("[PASS] initialize_task_node test passed")
    
    test_initialize_task_node_with_whitespace()
    print("[PASS] initialize_task_node whitespace test passed")
    
    test_initialize_task_node_missing_request()
    print("[PASS] initialize_task_node missing request test passed")
    
    test_initialize_task_node_missing_user_id()
    print("[PASS] initialize_task_node missing user_id test passed")
    
    # Orchestrator Tests
    test_orchestrator_initialization()
    print("[PASS] orchestrator_initialization test passed")
    
    test_orchestrator_get_graph_info()
    print("[PASS] orchestrator_get_graph_info test passed")
    
    # Run async tests
    async def run_async_tests():
        with patch('app.langgraph_nodes._call_ollama_llm', side_effect=simple_mock_llm):
            await test_orchestrator_run_task_basic()
            print("[PASS] orchestrator_run_task_basic test passed")
            
            await test_orchestrator_run_task_with_context()
            print("[PASS] orchestrator_run_task_with_context test passed")
            
            await test_end_to_end_b1_workflow()
            print("[PASS] end_to_end_b1_workflow test passed")
    
    asyncio.run(run_async_tests())
    
    print("\nAll LangGraph B1 Foundation tests passed! [SUCCESS]")