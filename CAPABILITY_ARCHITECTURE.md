# Antigen Capability Architecture Documentation

## Overview

The Capability Architecture is the foundational system that enables Antigen to progress from simple question-answering to autonomous task completion. This architecture provides the infrastructure for:

- **Tool System**: A registry of executable tools with permission controls
- **Skill System**: A registry of capabilities that combine tools to accomplish specific tasks
- **Task Orchestration**: A system for planning and executing tasks using skills and tools
- **Permission System**: Fine-grained access control for different operation types
- **Integration**: Seamless integration with existing Antigen systems (Context Engine, Memory Service, Time Service)

## Architecture

```
                         ANTIGEN
                            |
                    CAPABILITY ORCHESTRATOR
                            |
          +-----------------+-----------------+
          |                 |                 |
       TOOLS             SKILLS           PERMISSIONS
          |                 |                 |
    +-----------+     +-----------+     +-----------+
    | File Sys  |     | Software  |     | READ_ONLY |
    | System    |     | Engineering|     | SAFE_ACTION|
    | Diagnostics|     | IT        |     | REQUIRES_CONFIRMATION|
    +-----------+     +-----------+     | RESTRICTED |
                                          +-----------+
                            |
                     EXECUTION ENGINE
                            |
                     RESULT / RESPONSE
```

## Core Components

### 1. Tool System

Tools are the basic building blocks - individual functions that can perform specific actions.

#### Tool Structure

```python
Tool(
    name: str,                    # Unique identifier
    description: str,             # Human-readable description
    input_schema: Dict[str, ToolInputSchema],  # Input validation
    output_schema: ToolOutputSchema,            # Output validation
    permission_level: PermissionLevel,          # Access control
    domain: Optional[str],        # Domain category (e.g., "file_system")
    category: Optional[str],      # Specific category (e.g., "exploration")
    execution_handler: Callable   # Function that executes the tool
)
```

#### Permission Levels

- **READ_ONLY**: Safe operations that don't modify data (e.g., reading files)
- **SAFE_ACTION**: Non-destructive operations (e.g., creating files)
- **REQUIRES_CONFIRMATION**: Potentially impactful operations needing user approval
- **RESTRICTED**: Dangerous operations requiring special authorization

#### Example Tool

```python
def list_directory_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for listing directory contents."""
    path = input_data.get("path", ".")
    # Implementation...
    return {"path": path, "items": items, "count": len(items)}

list_directory_tool = Tool(
    name="list_directory",
    description="List contents of a directory",
    input_schema={
        "path": ToolInputSchema(type="string", description="Directory path", required=False, default="."),
        "max_items": ToolInputSchema(type="integer", description="Max items to return", required=False, default=100)
    },
    output_schema=ToolOutputSchema(type="object", description="Directory listing"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="file_system",
    category="exploration",
    execution_handler=list_directory_handler
)
```

### 2. Skill System

Skills are higher-level capabilities that combine multiple tools to accomplish specific types of tasks.

#### Skill Structure

```python
Skill(
    name: str,                    # Unique identifier
    description: str,             # Human-readable description
    domain: str,                  # Domain (e.g., "software_engineering")
    required_tools: List[str],    # List of tool names this skill uses
    capabilities: List[str],      # What this skill can accomplish
    instructions: str,            # How to use this skill
    execution_strategy: str,     # "sequential", "parallel", or "adaptive"
    permission_level: PermissionLevel
)
```

#### Example Skill

```python
project_analysis_skill = Skill(
    name="analyze_project",
    description="Analyze a software project structure and detect its type",
    domain="software_engineering",
    required_tools=["analyze_project_structure", "list_directory", "read_file"],
    capabilities=[
        "Detect project type (Python, Node.js, etc.)",
        "Identify project structure and organization",
        "List key project files and directories"
    ],
    instructions="""To analyze a project:
1. Use analyze_project_structure to detect project type
2. Use list_directory to explore the main directory structure
3. Use read_file to examine key configuration files if needed
4. Summarize findings about the project's type, structure, and organization""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.READ_ONLY
)
```

### 3. Task System

Tasks represent specific units of work that need to be completed.

#### Task Structure

```python
Task(
    task_id: str,                # Unique identifier
    description: str,            # What the task should accomplish
    domain: str,                 # Domain of the task
    status: TaskStatus,          # Current state (PENDING, IN_PROGRESS, COMPLETED, etc.)
    plan: Optional[TaskPlan],   # Execution plan
    created_at: datetime,        # When the task was created
    started_at: Optional[datetime],  # When execution started
    completed_at: Optional[datetime], # When execution completed
    result: Optional[Any],       # Final result
    error: Optional[str],        # Error message if failed
    metadata: Dict[str, Any]     # Additional context
)
```

#### Task Plan Structure

```python
TaskPlan(
    task_id: str,
    description: str,
    domain: str,
    skill_name: str,
    steps: List[TaskStep],       # Individual execution steps
    estimated_complexity: str,   # "low", "medium", "high"
    requires_confirmation: bool  # Whether user confirmation is needed
)
```

### 4. Task Orchestrator

The orchestrator is responsible for:
- Analyzing tasks to determine appropriate skills
- Creating execution plans
- Executing plans step by step
- Handling errors and recovery
- Managing permissions

```python
orchestrator = TaskOrchestrator(tool_registry, skill_registry)

# Analyze a task
analysis = orchestrator.analyze_task("Analyze this project", "software_engineering")

# Create an execution plan
task = Task(task_id="123", description="Analyze this project", domain="software_engineering")
plan = orchestrator.create_task_plan(task, skill)

# Execute the task
result = orchestrator.execute_task(task)
```

## Integration with Existing Systems

### Context Engine Integration

The capability system integrates with the existing Context Engine to provide task-relevant context:

```python
context = integrate_with_context_engine(
    db=db,
    user=user,
    query_text=task_description,
    conversation_id=conversation_id
)
```

This provides:
- User profile and preferences
- Relevant long-term memories
- Project context
- Conversation history
- Time context

### Memory Service Integration

Successful task results are automatically stored in memory for future reference:

```python
integrate_with_memory_service(
    db=db,
    user_id=user_id,
    task_result={"success": True, "data": result},
    task_description=task_description
)
```

### Time Service Integration

Tools can leverage the existing TimeService for accurate time operations:

```python
def get_current_time_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    from .time_service import TimeService
    timezone = input_data.get("timezone", "Africa/Nairobi")
    return TimeService.get_time_context(timezone)
```

## API Endpoints

The capability system exposes several REST API endpoints:

### Capability Status

```
GET /capabilities/status
```

Returns the current status of the capability system including enabled domains, available tools and skills.

### List Tools

```
GET /capabilities/tools?domain=<domain>&permission_level=<level>
```

List available tools, optionally filtered by domain or permission level.

### Get Tool Details

```
GET /capabilities/tools/{tool_name}
```

Get detailed information about a specific tool including input/output schemas.

### List Skills

```
GET /capabilities/skills?domain=<domain>
```

List available skills, optionally filtered by domain.

### Get Skill Details

```
GET /capabilities/skills/{skill_name}
```

Get detailed information about a specific skill.

### List Domains

```
GET /capabilities/domains
```

List all available domains and their enabled status.

### Analyze Task

```
POST /capabilities/analyze
{
  "description": "Task description",
  "domain": "optional domain"
}
```

Analyze a task to determine if it can be handled and how.

### Execute Task

```
POST /capabilities/execute
{
  "description": "Task description",
  "domain": "optional domain",
  "auto_execute": false
}
```

Execute a task using the capability system. If `auto_execute` is false, returns the execution plan without executing it.

### Direct Tool Execution

```
POST /capabilities/tools/{tool_name}/execute
{
  "input_data": {...}
}
```

Execute a tool directly with provided input data (for testing and manual use).

## Configuration

### Capability Configuration File

The system can be configured via `backend/capability_config.json`:

```json
{
  "domains": {
    "software_engineering": {
      "name": "software_engineering",
      "description": "Software development and engineering tasks",
      "enabled": true,
      "tools": ["list_directory", "read_file", "analyze_project_structure"],
      "skills": ["analyze_project", "explore_files"]
    }
  },
  "tools": {
    "list_directory": {
      "name": "list_directory",
      "description": "List contents of a directory",
      "input_schema": {...},
      "output_schema": {...},
      "permission_level": "READ_ONLY",
      "domain": "file_system",
      "category": "exploration"
    }
  },
  "skills": {
    "analyze_project": {
      "name": "analyze_project",
      "description": "Analyze a software project structure",
      "domain": "software_engineering",
      "required_tools": ["analyze_project_structure", "list_directory"],
      "capabilities": [...],
      "instructions": "...",
      "execution_strategy": "sequential",
      "permission_level": "READ_ONLY"
    }
  }
}
```

### Programmatic Configuration

```python
from app.capability_system import capability_config

# Enable a domain
capability_config.enable_domain("finance")

# Set default permission level
capability_config.default_permission_level = PermissionLevel.SAFE_ACTION

# Enable autonomous execution (use with caution)
capability_config.enable_autonomous_execution = True
```

## Adding New Capabilities

### Adding a New Tool

1. **Define the tool handler function**:

```python
def my_tool_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Implementation of your tool."""
    param = input_data.get("param", "default")
    # Your implementation here
    return {"result": f"Processed {param}"}
```

2. **Create the Tool object**:

```python
from app.capability_system import (
    Tool, ToolInputSchema, ToolOutputSchema, 
    PermissionLevel, tool_registry
)

my_tool = Tool(
    name="my_tool",
    description="Description of what my tool does",
    input_schema={
        "param": ToolInputSchema(
            type="string", 
            description="Parameter description",
            required=True
        )
    },
    output_schema=ToolOutputSchema(
        type="object", 
        description="Result description"
    ),
    permission_level=PermissionLevel.SAFE_ACTION,
    domain="my_domain",
    category="my_category",
    execution_handler=my_tool_handler
)
```

3. **Register the tool**:

```python
tool_registry.register(my_tool)
```

### Adding a New Skill

1. **Create the Skill object**:

```python
from app.capability_system import Skill, skill_registry

my_skill = Skill(
    name="my_skill",
    description="Description of what this skill accomplishes",
    domain="my_domain",
    required_tools=["my_tool", "other_tool"],
    capabilities=[
        "Capability 1",
        "Capability 2"
    ],
    instructions="""Instructions for using this skill:
1. First do this
2. Then do that
3. Finally accomplish the goal""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.SAFE_ACTION
)
```

2. **Register the skill**:

```python
skill_registry.register(my_skill)
```

3. **Enable the domain**:

```python
from app.capability_system import capability_config
capability_config.enable_domain("my_domain")
```

### Adding a New Domain

1. **Create tools and skills for the domain**

2. **Enable the domain in configuration**:

```python
capability_config.enable_domain("my_new_domain")
```

3. **Update the configuration file** (optional):

```json
{
  "domains": {
    "my_new_domain": {
      "name": "my_new_domain",
      "description": "Description of the new domain",
      "enabled": true,
      "tools": ["tool1", "tool2"],
      "skills": ["skill1", "skill2"]
    }
  }
}
```

## Current Capabilities

### Software Engineering Domain

**Tools:**
- `list_directory` - List directory contents
- `read_file` - Read file contents
- `analyze_project_structure` - Detect project type and organization

**Skills:**
- `analyze_project` - Analyze software project structure
- `explore_files` - Explore and understand file structure

### System Domain

**Tools:**
- `get_system_info` - Get system information
- `get_disk_usage` - Get disk usage statistics
- `get_current_time` - Get current time context

**Skills:**
- `system_diagnostics` - Run basic system diagnostics

### IT Domain

**Tools:**
- `get_system_info` - Get system information
- `get_disk_usage` - Get disk usage statistics
- `get_current_time` - Get current time context

**Skills:**
- `get_system_information` - Get comprehensive system information

## Testing

### Running Capability System Tests

```bash
cd backend
python test_capability_system.py
```

This runs comprehensive tests for:
- Tool registration and lookup
- Skill registration and lookup
- Task creation and routing
- Permission handling
- Execution result handling
- Integration with existing systems

### Test Coverage

The test suite includes:
- Tool system tests (registration, filtering, permissions)
- Skill system tests (registration, domain filtering, tool resolution)
- Task system tests (creation, status updates, plan generation)
- Task orchestrator tests (analysis, planning, execution)
- Tool handler tests (file system, system diagnostics)
- End-to-end integration tests

## Security Considerations

### Permission Enforcement

- All tool executions check permission levels
- RESTRICTED tools require special authorization
- User permissions are validated before execution

### Safe Defaults

- Autonomous execution is disabled by default
- Default permission level is SAFE_ACTION
- Only explicitly enabled domains are available

### Error Handling

- Tool execution failures don't crash the system
- Memory integration failures don't affect task execution
- Context engine failures have graceful fallbacks

## Future Enhancements

### Planned Improvements

1. **Advanced Planning**: Use LLM to generate multi-step execution plans
2. **Semantic Matching**: Use semantic search for skill selection
3. **Parallel Execution**: Execute independent steps in parallel
4. **Error Recovery**: Automatic retry and alternative strategies
5. **Learning**: Remember successful procedures for future use
6. **User Feedback**: Incorporate user corrections into learning

### New Domains

Future domains could include:
- **Finance**: Financial calculations and analysis
- **Cybersecurity**: Defensive security analysis
- **Data Analytics**: Statistical analysis and visualization
- **Machine Learning**: ML workflow management
- **Networking**: Network diagnostics and troubleshooting
- **Automation**: Task scheduling and workflows

## Troubleshooting

### Common Issues

**Tool not found:**
- Ensure the tool is registered in the tool registry
- Check that the tool name matches exactly

**Skill not found:**
- Ensure the skill is registered in the skill registry
- Verify all required tools are available

**Domain not enabled:**
- Enable the domain using `capability_config.enable_domain(domain_name)`
- Check the configuration file

**Permission denied:**
- Check the tool's permission level
- Verify user has sufficient permissions
- Consider using REQUIRES_CONFIRMATION instead of RESTRICTED

## Performance Considerations

### Optimization

- Tool execution is isolated to prevent cascading failures
- Context integration is optional and has fallbacks
- Memory integration is asynchronous and non-blocking
- Permission checks are cached where possible

### Scalability

- Tool and skill registries are in-memory for fast access
- Configuration can be loaded from files for persistence
- API endpoints support filtering to reduce payload size

## Conclusion

The Capability Architecture provides the foundation for Antigen to evolve from a simple question-answering system to a comprehensive task-completion platform. The modular design allows for incremental addition of new capabilities without modifying the core orchestrator, ensuring the system can grow and adapt over time.

The architecture maintains compatibility with existing Antigen systems while providing clear extension points for future development. By following the patterns and conventions established in this foundation, new capabilities can be added consistently and safely.