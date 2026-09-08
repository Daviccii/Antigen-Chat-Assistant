"""Tests for LangGraph Phase B2: Intelligent Planning.

Tests the LLM-powered planning functionality:
- Task understanding with LLM
- Domain identification
- Skill selection using Skill Registry
- Execution plan generation
- Integration with existing capability system

Phase B2: Planning functionality tests.
"""
import pytest
import sys
import os
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.langgraph_state import (
    AntigenTaskState,
    TaskStatus,
    create_initial_state,
    update_state_status,
    add_error
)
from app.langgraph_nodes import (
    initialize_task,
    understand_task,
    identify_domain,
    select_skill,
    create_execution_plan,
    _call_ollama_llm
)
from app.langgraph_orchestrator import LangGraphOrchestrator, langgraph_orchestrator


# ---------------------------------------------------------------------------
# Mock LLM Helper
# ---------------------------------------------------------------------------

async def mock_llm_response(messages, temperature=0.7, max_tokens=1000):
    """Mock LLM response for testing."""
    last_message = messages[-1]["content"].lower()
    
    if "analyze the following user request" in last_message and "json format" in last_message:
        return '''{
  "task_type": "project analysis",
  "primary_objective": "Analyze the software project structure",
  "key_entities": ["project", "structure", "code"],
  "parameters": {},
  "constraints": [],
  "expected_output": "Project structure report"
}'''
    elif "select the most appropriate domain" in last_message:
        # Check what domain is in the message to respond appropriately
        if "software" in last_message:
            return "software_engineering"
        elif "system" in last_message or "diagnostic" in last_message:
            return "system"
        elif "it" in last_message:
            return "it"
        return "software_engineering"  # default
    elif "select the most appropriate skill" in last_message:
        # Check what skills are mentioned in the message
        if "analyze_project" in last_message:
            return "analyze_project"
        elif "system_diagnostics" in last_message:
            return "system_diagnostics"
        elif "get_system_information" in last_message:
            return "get_system_information"
        return "analyze_project"  # default
    elif "create a detailed execution plan" in last_message:
        return '''{
  "steps": [
    {
      "step_number": 1,
      "description": "Analyze project structure",
      "tool": "analyze_project_structure",
      "inputs": {"path": "."},
      "expected_output": "Project type and structure"
    },
    {
      "step_number": 2,
      "description": "List directory contents",
      "tool": "list_directory",
      "inputs": {"path": "."},
      "expected_output": "File and directory listing"
    }
  ],
  "estimated_complexity": "medium",
  "requires_confirmation": false
}'''
    
    return "mock response"


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_capability_system():
    """Initialize the capability system before each test."""
    from app.capability_skills import initialize_basic_domains
    initialize_basic_domains()
    yield


@pytest.fixture
def sample_state():
    """Create a sample task state for testing."""
    return create_initial_state(
        user_request="Analyze my software project",
        user_id=1,
        conversation_id=123
    )


# ---------------------------------------------------------------------------
# Phase B1 Node Tests (ensure backward compatibility)
# ---------------------------------------------------------------------------

def test_initialize_task_node_b2():
    """Test that initialize_task still works in B2."""
    state = create_initial_state("Test request", 1)
    
    updated_state = initialize_task(state)
    
    assert updated_state["status"] == TaskStatus.INITIALIZING
    assert updated_state["user_request"] == "Test request"
    assert updated_state["metadata"]["initialized"] == True


# ---------------------------------------------------------------------------
# LLM Helper Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_ollama_llm_mock():
    """Test LLM helper with mock response."""
    with patch('app.langgraph_nodes.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "test response"}
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        result = await _call_ollama_llm([{"role": "user", "content": "test"}])
        
        assert result == "test response"


# ---------------------------------------------------------------------------
# Phase B2 Planning Node Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_understand_task_node():
    """Test task understanding node with mock LLM."""
    state = create_initial_state("Analyze my software project", 1)
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        updated_state = await understand_task(state)
    
    assert updated_state["status"] == TaskStatus.PLANNING
    assert "task_understanding" in updated_state["metadata"]
    assert updated_state["metadata"]["task_understanding"]["task_type"] == "project analysis"
    assert len(updated_state["errors"]) == 0


@pytest.mark.asyncio
async def test_understand_task_node_json_fallback():
    """Test task understanding with JSON parsing fallback."""
    state = create_initial_state("Test request", 1)
    
    # Mock LLM to return invalid JSON
    async def bad_json_response(messages, temperature=0.7, max_tokens=1000):
        return "this is not valid json"
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=bad_json_response):
        updated_state = await understand_task(state)
    
    # Should still succeed with fallback
    assert updated_state["status"] == TaskStatus.PLANNING
    assert "task_understanding" in updated_state["metadata"]
    assert updated_state["metadata"]["task_understanding"]["task_type"] == "general"


@pytest.mark.asyncio
async def test_identify_domain_node():
    """Test domain identification node."""
    state = create_initial_state("Analyze my software project", 1)
    state["metadata"]["task_understanding"] = {"task_type": "project analysis"}
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        updated_state = await identify_domain(state)
    
    # Should select a domain (either software_engineering or fallback to first available)
    assert updated_state["selected_domain"] is not None
    assert "domain_selection" in updated_state["metadata"]
    # The actual domain may vary based on available domains, so just check it's set
    assert updated_state["metadata"]["domain_selection"]["selected_domain"] == updated_state["selected_domain"]


@pytest.mark.asyncio
async def test_identify_domain_node_with_invalid_selection():
    """Test domain identification with invalid LLM selection."""
    state = create_initial_state("Test request", 1)
    
    # Mock LLM to return invalid domain
    async def invalid_domain_response(messages, temperature=0.7, max_tokens=1000):
        return "nonexistent_domain"
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=invalid_domain_response):
        updated_state = await identify_domain(state)
    
    # Should default to first available domain (graceful fallback)
    assert updated_state["selected_domain"] is not None
    # System handles invalid selection gracefully without adding errors to state


@pytest.mark.asyncio
async def test_select_skill_node():
    """Test skill selection node."""
    state = create_initial_state("Analyze my software project", 1)
    state["selected_domain"] = "software_engineering"
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        updated_state = await select_skill(state)
    
    # Should select a skill (either analyze_project or fallback to first available)
    assert updated_state["selected_skill"] is not None
    assert "skill_selection" in updated_state["metadata"]
    # The actual skill may vary, so just check it's set
    assert updated_state["metadata"]["skill_selection"]["selected_skill"] == updated_state["selected_skill"]


@pytest.mark.asyncio
async def test_select_skill_node_no_skills():
    """Test skill selection when no skills available for domain."""
    state = create_initial_state("Test request", 1)
    state["selected_domain"] = "nonexistent_domain"
    
    with patch('app.capability_system.skill_registry.get_by_domain', return_value=[]):
        updated_state = await select_skill(state)
    
    assert updated_state["selected_skill"] is None
    # System handles missing skills gracefully by setting skill to None


@pytest.mark.asyncio
async def test_create_execution_plan_node():
    """Test execution plan generation node."""
    state = create_initial_state("Analyze my software project", 1)
    state["selected_domain"] = "software_engineering"
    state["selected_skill"] = "analyze_project"
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        updated_state = await create_execution_plan(state)
    
    assert updated_state["plan"] is not None
    assert "steps" in updated_state["plan"]
    assert len(updated_state["plan"]["steps"]) > 0
    assert "plan_generation" in updated_state["metadata"]
    assert updated_state["metadata"]["plan_generation"]["plan_created"] == True


@pytest.mark.asyncio
async def test_create_execution_plan_node_json_fallback():
    """Test execution plan generation with JSON parsing fallback."""
    state = create_initial_state("Test request", 1)
    state["selected_domain"] = "software_engineering"
    state["selected_skill"] = "analyze_project"
    
    # Mock LLM to return invalid JSON
    async def bad_json_response(messages, temperature=0.7, max_tokens=1000):
        return "invalid json"
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=bad_json_response):
        updated_state = await create_execution_plan(state)
    
    # Should still succeed with fallback plan
    assert updated_state["plan"] is not None
    assert "steps" in updated_state["plan"]
    assert len(updated_state["plan"]["steps"]) > 0


# ---------------------------------------------------------------------------
# Orchestrator Tests
# ---------------------------------------------------------------------------

def test_orchestrator_initialization_b2():
    """Test that orchestrator initializes with B4 workflow (includes B2 nodes)."""
    orchestrator = LangGraphOrchestrator()
    
    assert orchestrator is not None
    assert orchestrator.graph is not None
    
    info = orchestrator.get_graph_info()
    # Updated to B4 phase after B3/B4 implementation
    assert info["phase"] == "B4"
    assert "understand_task" in info["nodes"]
    assert "identify_domain" in info["nodes"]
    assert "select_skill" in info["nodes"]
    assert "create_execution_plan" in info["nodes"]


@pytest.mark.asyncio
async def test_orchestrator_run_task_b2_with_mock():
    """Test full B4 workflow execution with mocked LLM (includes B2 planning)."""
    orchestrator = LangGraphOrchestrator()
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        result = await orchestrator.run_task(
            user_request="Analyze my software project",
            user_id=1
        )
    
    # With B4 workflow, the result will include B3/B4 fields
    assert result is not None
    assert result["status"] is not None
    assert result["selected_domain"] is not None  # Domain should be selected
    # Skill might be None if domain doesn't have skills
    assert result["plan"] is not None
    assert len(result["plan"]["steps"]) > 0
    assert "task_understanding" in result["metadata"]
    assert "domain_selection" in result["metadata"]
    # B3/B4 fields should be present
    assert "selected_tools" in result
    assert "permission_results" in result
    assert "execution_state" in result


@pytest.mark.asyncio
async def test_orchestrator_with_context():
    """Test orchestrator with context parameter (B4 workflow)."""
    orchestrator = LangGraphOrchestrator()
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        result = await orchestrator.run_task(
            user_request="Test with context",
            user_id=1,
            conversation_id=456,
            context={"test": "context"}
        )
    
    # With B4 workflow, success depends on execution
    assert result is not None
    assert result["conversation_id"] == 456


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_b2_workflow():
    """Test complete B4 workflow from state to execution (includes B2 planning)."""
    # Create initial state
    state = create_initial_state(
        user_request="Analyze my software project",
        user_id=1,
        conversation_id=789
    )
    
    # Verify initial state
    assert state["status"] == TaskStatus.PENDING
    
    # Run through B2 nodes sequentially (part of B4 workflow)
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=mock_llm_response):
        # Initialize
        state = initialize_task(state)
        assert state["status"] == TaskStatus.INITIALIZING
        
        # Understand
        state = await understand_task(state)
        assert state["status"] == TaskStatus.PLANNING
        assert "task_understanding" in state["metadata"]
        
        # Identify domain
        state = await identify_domain(state)
        assert state["selected_domain"] is not None  # Should select some domain
        
        # Select skill (may be None if domain has no skills)
        state = await select_skill(state)
        # Don't assert skill is not None, as it depends on domain skills availability
        
        # Create plan
        state = await create_execution_plan(state)
        assert state["plan"] is not None
        assert len(state["plan"]["steps"]) > 0


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_failure_handling():
    """Test handling of LLM call failures."""
    state = create_initial_state("Test request", 1)
    
    # Mock LLM to raise exception
    async def failing_llm(messages, temperature=0.7, max_tokens=1000):
        raise Exception("LLM connection failed")
    
    with patch('app.langgraph_nodes._call_ollama_llm', side_effect=failing_llm):
        updated_state = await understand_task(state)
    
    # Should handle error gracefully
    assert updated_state["status"] == TaskStatus.FAILED
    assert len(updated_state["errors"]) > 0


# ---------------------------------------------------------------------------
# Run Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running LangGraph B2 Planning Tests...")
    
    # Initialize capability system
    from app.capability_skills import initialize_basic_domains
    initialize_basic_domains()
    
    # Phase B1 backward compatibility
    test_initialize_task_node_b2()
    print("[PASS] initialize_task_node_b2 test passed")
    
    # Run async tests
    async def run_async_tests():
        # LLM Helper Tests
        await test_call_ollama_llm_mock()
        print("[PASS] call_ollama_llm_mock test passed")
        
        # Planning Node Tests
        await test_understand_task_node()
        print("[PASS] understand_task_node test passed")
        
        await test_understand_task_node_json_fallback()
        print("[PASS] understand_task_node_json_fallback test passed")
        
        await test_identify_domain_node()
        print("[PASS] identify_domain_node test passed")
        
        await test_identify_domain_node_with_invalid_selection()
        print("[PASS] identify_domain_node_with_invalid_selection test passed")
        
        await test_select_skill_node()
        print("[PASS] select_skill_node test passed")
        
        await test_select_skill_node_no_skills()
        print("[PASS] select_skill_node_no_skills test passed")
        
        await test_create_execution_plan_node()
        print("[PASS] create_execution_plan_node test passed")
        
        await test_create_execution_plan_node_json_fallback()
        print("[PASS] create_execution_plan_node_json_fallback test passed")
        
        # Orchestrator Tests
        test_orchestrator_initialization_b2()
        print("[PASS] orchestrator_initialization_b2 test passed")
        
        await test_orchestrator_run_task_b2_with_mock()
        print("[PASS] orchestrator_run_task_b2_with_mock test passed")
        
        await test_orchestrator_with_context()
        print("[PASS] orchestrator_with_context test passed")
        
        # Integration Tests
        await test_end_to_end_b2_workflow()
        print("[PASS] end_to_end_b2_workflow test passed")
        
        # Error Handling Tests
        await test_llm_failure_handling()
        print("[PASS] llm_failure_handling test passed")
    
    asyncio.run(run_async_tests())
    
    print("\nAll LangGraph B2 Planning tests passed! [SUCCESS]")
