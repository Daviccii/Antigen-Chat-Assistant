"""Tests for Capability System Foundation.

Tests the core components of the capability architecture:
- Tool registration and lookup
- Skill registration and lookup
- Task creation and routing
- Permission handling
- Execution result handling
- Integration with existing systems
"""
import pytest
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.capability_system import (
    Tool, ToolInputSchema, ToolOutputSchema, PermissionLevel,
    tool_registry, ToolRegistry,
    Skill, skill_registry, SkillRegistry,
    Task, TaskStatus, TaskPlan, TaskStep,
    TaskOrchestrator, ExecutionResult,
    CapabilityConfig, capability_config,
    integrate_with_context_engine, integrate_with_memory_service
)
from app.capability_tools import (
    list_directory_handler, read_file_handler,
    get_system_info_handler, get_disk_usage_handler
)


# ---------------------------------------------------------------------------
# Tool System Tests
# ---------------------------------------------------------------------------

def test_tool_registration():
    """Test that tools can be registered and retrieved."""
    # Create a test tool
    test_tool = Tool(
        name="test_tool",
        description="A test tool",
        input_schema={"param1": ToolInputSchema(type="string", description="Test parameter")},
        output_schema=ToolOutputSchema(type="string", description="Test output"),
        permission_level=PermissionLevel.READ_ONLY,
        domain="test",
        category="testing"
    )
    
    # Register the tool
    tool_registry.register(test_tool)
    
    # Retrieve the tool
    retrieved_tool = tool_registry.get("test_tool")
    
    assert retrieved_tool is not None
    assert retrieved_tool.name == "test_tool"
    assert retrieved_tool.description == "A test tool"
    assert retrieved_tool.permission_level == PermissionLevel.READ_ONLY
    
    # Clean up
    del tool_registry._tools["test_tool"]


def test_tool_registry_filtering():
    """Test that tool registry can filter by domain and permission level."""
    # Create test tools with different properties
    tool1 = Tool(
        name="tool1",
        description="Tool 1",
        input_schema={},
        output_schema=ToolOutputSchema(type="string", description="Output"),
        permission_level=PermissionLevel.READ_ONLY,
        domain="domain1"
    )
    
    tool2 = Tool(
        name="tool2",
        description="Tool 2",
        input_schema={},
        output_schema=ToolOutputSchema(type="string", description="Output"),
        permission_level=PermissionLevel.SAFE_ACTION,
        domain="domain2"
    )
    
    tool_registry.register(tool1)
    tool_registry.register(tool2)
    
    # Test domain filtering
    domain1_tools = tool_registry.list_tools(domain="domain1")
    assert len(domain1_tools) == 1
    assert domain1_tools[0].name == "tool1"
    
    # Test permission filtering
    read_only_tools = tool_registry.list_tools(permission_level=PermissionLevel.READ_ONLY)
    assert len(read_only_tools) >= 1
    assert any(t.name == "tool1" for t in read_only_tools)
    
    # Clean up
    del tool_registry._tools["tool1"]
    del tool_registry._tools["tool2"]


def test_tool_permission_checking():
    """Test tool permission level checking."""
    tool = Tool(
        name="restricted_tool",
        description="A restricted tool",
        input_schema={},
        output_schema=ToolOutputSchema(type="string", description="Output"),
        permission_level=PermissionLevel.RESTRICTED,
        domain="test"
    )
    
    # Test that owner can execute
    assert tool.can_execute(PermissionLevel.RESTRICTED) == True
    
    # Test that regular user cannot execute
    assert tool.can_execute(PermissionLevel.READ_ONLY) == False
    assert tool.can_execute(PermissionLevel.SAFE_ACTION) == False


# ---------------------------------------------------------------------------
# Skill System Tests
# ---------------------------------------------------------------------------

def test_skill_registration():
    """Test that skills can be registered and retrieved."""
    test_skill = Skill(
        name="test_skill",
        description="A test skill",
        domain="test_domain",
        required_tools=["tool1", "tool2"],
        capabilities=["capability1", "capability2"],
        instructions="Test instructions",
        permission_level=PermissionLevel.SAFE_ACTION
    )
    
    skill_registry.register(test_skill)
    
    retrieved_skill = skill_registry.get("test_skill")
    
    assert retrieved_skill is not None
    assert retrieved_skill.name == "test_skill"
    assert retrieved_skill.domain == "test_domain"
    assert len(retrieved_skill.required_tools) == 2
    
    # Clean up
    del skill_registry._skills["test_skill"]


def test_skill_domain_filtering():
    """Test that skill registry can filter by domain."""
    skill1 = Skill(
        name="skill1",
        description="Skill 1",
        domain="domain1",
        required_tools=[],
        capabilities=[],
        instructions="Instructions"
    )
    
    skill2 = Skill(
        name="skill2",
        description="Skill 2",
        domain="domain2",
        required_tools=[],
        capabilities=[],
        instructions="Instructions"
    )
    
    skill_registry.register(skill1)
    skill_registry.register(skill2)
    
    domain1_skills = skill_registry.list_skills(domain="domain1")
    assert len(domain1_skills) == 1
    assert domain1_skills[0].name == "skill1"
    
    # Clean up
    del skill_registry._skills["skill1"]
    del skill_registry._skills["skill2"]


def test_skill_tool_resolution():
    """Test that skills can resolve their required tools."""
    # Create and register a tool
    tool = Tool(
        name="resolve_test_tool",
        description="Tool for resolution test",
        input_schema={},
        output_schema=ToolOutputSchema(type="string", description="Output"),
        permission_level=PermissionLevel.READ_ONLY
    )
    tool_registry.register(tool)
    
    # Create a skill that requires the tool
    skill = Skill(
        name="resolve_test_skill",
        description="Skill for resolution test",
        domain="test",
        required_tools=["resolve_test_tool"],
        capabilities=[],
        instructions="Instructions"
    )
    
    required_tools = skill.get_required_tools(tool_registry)
    
    assert len(required_tools) == 1
    assert required_tools[0].name == "resolve_test_tool"
    
    # Clean up
    del tool_registry._tools["resolve_test_tool"]


# ---------------------------------------------------------------------------
# Task System Tests
# ---------------------------------------------------------------------------

def test_task_creation():
    """Test that tasks can be created with proper attributes."""
    task = Task(
        task_id="test_task_1",
        description="Test task description",
        domain="test_domain"
    )
    
    assert task.task_id == "test_task_1"
    assert task.description == "Test task description"
    assert task.domain == "test_domain"
    assert task.status == TaskStatus.PENDING
    assert task.created_at is not None


def test_task_status_updates():
    """Test that task status updates correctly."""
    task = Task(
        task_id="test_task_2",
        description="Test task",
        domain="test"
    )
    
    # Update to in progress
    task.update_status(TaskStatus.IN_PROGRESS)
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.started_at is not None
    
    # Update to completed
    task.update_status(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None


def test_task_plan_creation():
    """Test that task plans can be created with steps."""
    plan = TaskPlan(
        task_id="test_plan_1",
        description="Test plan",
        domain="test",
        skill_name="test_skill"
    )
    
    step = TaskStep(
        step_id="step_1",
        description="Test step",
        tool_name="test_tool",
        input_data={"param": "value"}
    )
    
    plan.add_step(step)
    
    assert len(plan.steps) == 1
    assert plan.steps[0].step_id == "step_1"
    assert len(plan.get_pending_steps()) == 1


def test_task_step_completion():
    """Test that task steps can be marked as completed."""
    step = TaskStep(
        step_id="step_1",
        description="Test step",
        tool_name="test_tool",
        input_data={}
    )
    
    assert step.completed == False
    
    step.completed = True
    step.result = {"output": "success"}
    
    assert step.completed == True
    assert step.result == {"output": "success"}


# ---------------------------------------------------------------------------
# Task Orchestrator Tests
# ---------------------------------------------------------------------------

def test_task_analysis():
    """Test that task orchestrator can analyze tasks."""
    # Create a skill for testing
    skill = Skill(
        name="analysis_test_skill",
        description="Skill for testing task analysis",
        domain="test",
        required_tools=[],
        capabilities=["test capability"],
        instructions="Test instructions"
    )
    skill_registry.register(skill)
    
    orchestrator = TaskOrchestrator(tool_registry, skill_registry)
    
    analysis = orchestrator.analyze_task("test capability", "test")
    
    assert analysis["can_handle"] == True
    assert analysis["skill"] == "analysis_test_skill"
    assert analysis["domain"] == "test"
    
    # Clean up
    del skill_registry._skills["analysis_test_skill"]


def test_task_plan_generation():
    """Test that task orchestrator can generate execution plans."""
    # Create a skill for testing
    skill = Skill(
        name="plan_test_skill",
        description="Skill for testing plan generation",
        domain="test",
        required_tools=["test_tool"],
        capabilities=["test capability"],
        instructions="Test instructions"
    )
    skill_registry.register(skill)
    
    # Create a tool for testing
    tool = Tool(
        name="test_tool",
        description="Test tool",
        input_schema={},
        output_schema=ToolOutputSchema(type="string", description="Output"),
        execution_handler=lambda x: {"result": "success"}
    )
    tool_registry.register(tool)
    
    orchestrator = TaskOrchestrator(tool_registry, skill_registry)
    
    task = Task(
        task_id="test_task_3",
        description="Test task for plan generation",
        domain="test"
    )
    
    plan = orchestrator.create_task_plan(task, skill)
    
    assert plan.task_id == task.task_id
    assert plan.skill_name == "plan_test_skill"
    assert len(plan.steps) > 0
    
    # Clean up
    del skill_registry._skills["plan_test_skill"]
    del tool_registry._tools["test_tool"]


# ---------------------------------------------------------------------------
# Tool Handler Tests
# ---------------------------------------------------------------------------

def test_list_directory_handler():
    """Test the list directory tool handler."""
    # Test with current directory
    result = list_directory_handler({"path": "."})
    
    assert "items" in result
    assert "count" in result
    assert isinstance(result["items"], list)
    assert result["count"] == len(result["items"])


def test_get_system_info_handler():
    """Test the system info tool handler."""
    result = get_system_info_handler({})
    
    assert "system" in result
    assert "python_version" in result
    assert "timestamp" in result


def test_get_disk_usage_handler():
    """Test the disk usage tool handler."""
    result = get_disk_usage_handler({"path": "."})
    
    assert "total_gb" in result
    assert "used_gb" in result
    assert "free_gb" in result
    assert "percent_used" in result


# ---------------------------------------------------------------------------
# Permission System Tests
# ---------------------------------------------------------------------------

def test_permission_levels():
    """Test that permission levels work correctly."""
    assert PermissionLevel.READ_ONLY.value == "READ_ONLY"
    assert PermissionLevel.SAFE_ACTION.value == "SAFE_ACTION"
    assert PermissionLevel.REQUIRES_CONFIRMATION.value == "REQUIRES_CONFIRMATION"
    assert PermissionLevel.RESTRICTED.value == "RESTRICTED"


# ---------------------------------------------------------------------------
# Configuration System Tests
# ---------------------------------------------------------------------------

def test_capability_config():
    """Test the capability configuration system."""
    config = CapabilityConfig()
    
    assert config.default_permission_level == PermissionLevel.SAFE_ACTION
    assert config.enable_autonomous_execution == False
    
    config.enable_domain("test_domain")
    assert "test_domain" in config.enabled_domains
    assert config.is_domain_enabled("test_domain") == True
    
    assert config.is_domain_enabled("nonexistent_domain") == False


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_basic_tool_execution():
    """Test basic tool execution through the orchestrator."""
    # Create a simple tool with a handler
    def simple_handler(input_data):
        return {"result": f"Processed: {input_data.get('value', 'default')}"}
    
    tool = Tool(
        name="simple_test_tool",
        description="Simple test tool",
        input_schema={"value": ToolInputSchema(type="string", description="Input value")},
        output_schema=ToolOutputSchema(type="object", description="Result"),
        permission_level=PermissionLevel.SAFE_ACTION,
        execution_handler=simple_handler
    )
    tool_registry.register(tool)
    
    orchestrator = TaskOrchestrator(tool_registry, skill_registry)
    
    step = TaskStep(
        step_id="test_step",
        description="Test step",
        tool_name="simple_test_tool",
        input_data={"value": "test_input"}
    )
    
    result = orchestrator.execute_step(step)
    
    assert result.success == True
    assert result.data is not None
    assert "Processed: test_input" in result.data.get("result", "")
    
    # Clean up
    del tool_registry._tools["simple_test_tool"]


def test_end_to_end_task_flow():
    """Test a complete task flow from analysis to execution."""
    # Create a skill
    skill = Skill(
        name="e2e_test_skill",
        description="End-to-end test skill",
        domain="test",
        required_tools=["e2e_test_tool"],
        capabilities=["end to end test"],
        instructions="Test instructions"
    )
    skill_registry.register(skill)
    
    # Create a tool with a handler
    def e2e_handler(input_data):
        return {"status": "completed", "data": "test data"}
    
    tool = Tool(
        name="e2e_test_tool",
        description="End-to-end test tool",
        input_schema={},
        output_schema=ToolOutputSchema(type="object", description="Result"),
        permission_level=PermissionLevel.SAFE_ACTION,
        execution_handler=e2e_handler
    )
    tool_registry.register(tool)
    
    orchestrator = TaskOrchestrator(tool_registry, skill_registry)
    
    # Analyze task
    analysis = orchestrator.analyze_task("end to end test", "test")
    assert analysis["can_handle"] == True
    
    # Create and plan task
    task = Task(
        task_id="e2e_task",
        description="End-to-end test task",
        domain="test"
    )
    
    plan = orchestrator.create_task_plan(task, skill)
    task.plan = plan
    
    # Execute task
    result = orchestrator.execute_task(task)
    
    assert result.success == True
    assert task.status == TaskStatus.COMPLETED
    
    # Clean up
    del skill_registry._skills["e2e_test_skill"]
    del tool_registry._tools["e2e_test_tool"]


if __name__ == "__main__":
    # Run tests manually if executed directly
    print("Running capability system tests...")
    
    test_tool_registration()
    print("[PASS] Tool registration test passed")
    
    test_tool_registry_filtering()
    print("[PASS] Tool registry filtering test passed")
    
    test_tool_permission_checking()
    print("[PASS] Tool permission checking test passed")
    
    test_skill_registration()
    print("[PASS] Skill registration test passed")
    
    test_skill_domain_filtering()
    print("[PASS] Skill domain filtering test passed")
    
    test_skill_tool_resolution()
    print("[PASS] Skill tool resolution test passed")
    
    test_task_creation()
    print("[PASS] Task creation test passed")
    
    test_task_status_updates()
    print("[PASS] Task status updates test passed")
    
    test_task_plan_creation()
    print("[PASS] Task plan creation test passed")
    
    test_task_step_completion()
    print("[PASS] Task step completion test passed")
    
    test_task_analysis()
    print("[PASS] Task analysis test passed")
    
    test_task_plan_generation()
    print("[PASS] Task plan generation test passed")
    
    test_list_directory_handler()
    print("[PASS] List directory handler test passed")
    
    test_get_system_info_handler()
    print("[PASS] System info handler test passed")
    
    test_get_disk_usage_handler()
    print("[PASS] Disk usage handler test passed")
    
    test_permission_levels()
    print("[PASS] Permission levels test passed")
    
    test_capability_config()
    print("[PASS] Capability config test passed")
    
    test_basic_tool_execution()
    print("[PASS] Basic tool execution test passed")
    
    test_end_to_end_task_flow()
    print("[PASS] End-to-end task flow test passed")
    
    print("\nAll capability system tests passed! [SUCCESS]")