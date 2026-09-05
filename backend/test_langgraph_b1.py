"""Tests for LangGraph Phase B1 Foundation.

Tests the basic LangGraph integration:
- State creation and management
- Node execution
- Graph construction and execution
- Integration with existing systems

Phase B1: Basic functionality tests only.
"""
import pytest
import sys
import os
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


def test_orchestrator_run_task_basic():
    """Test basic task execution through the orchestrator."""
    result = langgraph_orchestrator.run_task(
        user_request="Test task",
        user_id=1
    )
    
    assert result["success"] == True
    assert result["status"] == TaskStatus.INITIALIZING.value
    assert result["user_request"] == "Test task"
    assert result["user_id"] == 1
    assert result["metadata"]["initialized"] == True


def test_orchestrator_run_task_with_context():
    """Test task execution with context."""
    result = langgraph_orchestrator.run_task(
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
    
    assert info["phase"] == "B1"
    assert "initialize_task" in info["nodes"]
    assert len(info["future_phases"]) > 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_end_to_end_b1_workflow():
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
    result = langgraph_orchestrator.run_task(
        user_request="End-to-end test",
        user_id=1,
        conversation_id=456
    )
    
    # Verify final result
    assert result["success"] == True
    assert result["status"] == TaskStatus.INITIALIZING.value
    assert result["metadata"]["initialized"] == True
    assert len(result["errors"]) == 0


# ---------------------------------------------------------------------------
# Run Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running LangGraph B1 Foundation Tests...")
    
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
    
    test_orchestrator_run_task_basic()
    print("[PASS] orchestrator_run_task_basic test passed")
    
    test_orchestrator_run_task_with_context()
    print("[PASS] orchestrator_run_task_with_context test passed")
    
    test_orchestrator_get_graph_info()
    print("[PASS] orchestrator_get_graph_info test passed")
    
    # Integration Tests
    test_end_to_end_b1_workflow()
    print("[PASS] end_to_end_b1_workflow test passed")
    
    print("\nAll LangGraph B1 Foundation tests passed! [SUCCESS]")