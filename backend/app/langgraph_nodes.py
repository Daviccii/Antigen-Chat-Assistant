"""LangGraph Nodes for Antigen Task Orchestration.

This module defines the individual nodes that will be used in the LangGraph workflow.
Each node represents a specific step in the task orchestration process.

Phase B1: Only the initialize_task node is implemented to prove the graph works.
Phase B2: Added LLM-powered planning nodes for task understanding, domain identification,
           skill selection, and execution plan generation.
Phase B3: Added tool selection and permission validation nodes.
Phase B4: Added execution and result collection nodes.
"""
from typing import Dict, Any, Optional
import logging
import json
import httpx

from .langgraph_state import (
    AntigenTaskState, 
    TaskStatus, 
    create_initial_state,
    update_state_status,
    add_error
)
from .config import settings

logger = logging.getLogger(__name__)


def initialize_task(state: AntigenTaskState) -> AntigenTaskState:
    """Initialize the task state and normalize the request.
    
    This is the minimal B1 node that:
    - Validates the incoming state structure
    - Normalizes the user request
    - Sets status to INITIALIZING
    - Prepares the state for future planning and execution
    
    Phase B1: Basic initialization only. No autonomous planning or LLM calls.
    
    Args:
        state: Current task state
    
    Returns:
        Updated task state with initialization complete
    """
    logger.info(f"Initializing task for user {state['user_id']}: {state['user_request'][:50]}...")
    
    # Validate required fields
    if not state.get("user_request"):
        state["errors"].append("Missing user_request in state")
        return update_state_status(state, TaskStatus.FAILED)
    
    if not state.get("user_id"):
        state["errors"].append("Missing user_id in state")
        return update_state_status(state, TaskStatus.FAILED)
    
    # Normalize the user request (basic cleanup)
    state["user_request"] = state["user_request"].strip()
    
    # Ensure execution_results and errors are initialized
    if "execution_results" not in state:
        state["execution_results"] = []
    if "errors" not in state:
        state["errors"] = []
    if "metadata" not in state:
        state["metadata"] = {}
    
    # Add initialization metadata
    state["metadata"]["initialized"] = True
    state["metadata"]["initialization_timestamp"] = state["created_at"].isoformat()
    
    # Update status to indicate initialization is complete
    # In later phases, this would transition to PLANNING
    updated_state = update_state_status(state, TaskStatus.INITIALIZING)
    
    logger.info(f"Task initialization complete for user {state['user_id']}")
    
    return updated_state


# ---------------------------------------------------------------------------
# LLM Helper Functions (Phase B2)
# ---------------------------------------------------------------------------

async def _call_ollama_llm(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1000
) -> str:
    """Call Ollama LLM for planning and reasoning tasks.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        temperature: Generation temperature
        max_tokens: Maximum tokens to generate
    
    Returns:
        Generated text response
    """
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": settings.OLLAMA_NUM_CTX,
                "num_predict": max_tokens
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result.get("message", {}).get("content", "")
            return content
            
    except Exception as e:
        logger.exception(f"Error calling Ollama LLM: {e}")
        raise


# ---------------------------------------------------------------------------
# Phase B2: Planning Nodes
# ---------------------------------------------------------------------------

async def understand_task(state: AntigenTaskState) -> AntigenTaskState:
    """Use LLM to understand the user's task and extract key information.
    
    This node analyzes the user request to understand:
    - What the user wants to accomplish
    - Key entities and parameters
    - Context and constraints
    - Expected output format
    
    Phase B2: LLM-powered task understanding.
    
    Args:
        state: Current task state
    
    Returns:
        Updated task state with understanding metadata
    """
    logger.info(f"Understanding task for user {state['user_id']}: {state['user_request'][:50]}...")
    
    try:
        # Build understanding prompt
        prompt = f"""Analyze the following user request and extract key information in JSON format:

User Request: {state['user_request']}

Respond with a JSON object containing:
{{
  "task_type": "brief description of what type of task this is",
  "primary_objective": "what the user wants to accomplish",
  "key_entities": ["list of important entities mentioned"],
  "parameters": {{"param_name": "value or null if not specified"}},
  "constraints": ["list of any constraints or requirements"],
  "expected_output": "what kind of output the user expects"
}}

Output ONLY valid JSON, no markdown, no explanation."""

        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM
        understanding_text = await _call_ollama_llm(messages, temperature=0.3)
        
        # Parse JSON response
        try:
            # Clean up response if needed
            understanding_text = understanding_text.strip()
            if understanding_text.startswith("```"):
                understanding_text = understanding_text.strip("`")
                if understanding_text.lower().startswith("json"):
                    understanding_text = understanding_text[4:]
                understanding_text = understanding_text.strip()
            
            understanding = json.loads(understanding_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse understanding JSON: {e}, using fallback")
            understanding = {
                "task_type": "general",
                "primary_objective": state['user_request'],
                "key_entities": [],
                "parameters": {},
                "constraints": [],
                "expected_output": "text response"
            }
        
        # Store understanding in state metadata
        state["metadata"]["task_understanding"] = understanding
        state["metadata"]["understanding_timestamp"] = state["updated_at"].isoformat()
        
        logger.info(f"Task understanding complete for user {state['user_id']}")
        
        return update_state_status(state, TaskStatus.PLANNING)
        
    except Exception as e:
        logger.exception(f"Error in understand_task: {e}")
        add_error(state, f"Task understanding failed: {str(e)}")
        return update_state_status(state, TaskStatus.FAILED)


async def identify_domain(state: AntigenTaskState) -> AntigenTaskState:
    """Identify the most appropriate domain for the task.
    
    This node uses the LLM to determine which domain should handle the task
    based on the task understanding and available domains.
    
    Phase B2: LLM-powered domain identification.
    
    Args:
        state: Current task state
    
    Returns:
        Updated task state with selected domain
    """
    logger.info(f"Identifying domain for user {state['user_id']}")
    
    try:
        # Get available domains from capability system
        from .capability_system import capability_config
        
        available_domains = capability_config.enabled_domains
        domain_descriptions = {
            "software_engineering": "Software development, code analysis, project structure, debugging",
            "system": "System diagnostics, system information, performance monitoring",
            "it": "IT operations, system administration, infrastructure management",
            "data": "Data analysis, statistics, data processing, visualization",
            "math": "Mathematical calculations, algorithms, numerical analysis",
            "finance": "Financial analysis, stocks, forex, market data",
            "research": "Information gathering, research, fact-checking, knowledge synthesis",
            "documents": "Document processing, file analysis, content extraction"
        }
        
        # Build domain selection prompt
        domains_list = "\n".join([
            f"- {domain}: {domain_descriptions.get(domain, 'General purpose')}"
            for domain in available_domains
        ])
        
        prompt = f"""Based on the following task, select the most appropriate domain:

Task: {state['user_request']}
Task Type: {state['metadata'].get('task_understanding', {}).get('task_type', 'unknown')}

Available Domains:
{domains_list}

Respond with ONLY the domain name (e.g., "software_engineering", "system", "it").
If no domain clearly matches, respond with "general"."""

        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM
        domain_text = await _call_ollama_llm(messages, temperature=0.2)
        
        # Clean and validate domain
        selected_domain = domain_text.strip().lower().replace(" ", "_")
        
        # Validate against available domains
        if selected_domain not in available_domains:
            logger.warning(f"LLM selected domain '{selected_domain}' not in available domains, defaulting to first available")
            selected_domain = available_domains[0] if available_domains else "general"
        
        state["selected_domain"] = selected_domain
        state["metadata"]["domain_selection"] = {
            "selected_domain": selected_domain,
            "selection_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Domain identified as '{selected_domain}' for user {state['user_id']}")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in identify_domain: {e}")
        # Default to first available domain or general
        from .capability_system import capability_config
        available_domains = capability_config.enabled_domains
        state["selected_domain"] = available_domains[0] if available_domains else "general"
        add_error(state, f"Domain identification failed, using default: {str(e)}")
        return state


async def select_skill(state: AntigenTaskState) -> AntigenTaskState:
    """Select the most appropriate skill for the task within the chosen domain.
    
    This node uses the Skill Registry to find skills that match the task
    and uses the LLM to select the best one.
    
    Phase B2: LLM-powered skill selection using Skill Registry.
    
    Args:
        state: Current task state with selected_domain
    
    Returns:
        Updated task state with selected skill
    """
    logger.info(f"Selecting skill for domain '{state['selected_domain']}'")
    
    try:
        from .capability_system import skill_registry
        
        # Get available skills for the selected domain
        domain_skills = skill_registry.get_by_domain(state['selected_domain'])
        
        if not domain_skills:
            logger.warning(f"No skills found for domain '{state['selected_domain']}'")
            state["selected_skill"] = None
            add_error(state, f"No skills available for domain '{state['selected_domain']}'")
            return state
        
        # Build skill descriptions for LLM
        skills_list = "\n".join([
            f"- {skill.name}: {skill.description}\n  Capabilities: {', '.join(skill.capabilities[:3])}"
            for skill in domain_skills
        ])
        
        prompt = f"""Based on the following task, select the most appropriate skill:

Task: {state['user_request']}
Domain: {state['selected_domain']}

Available Skills:
{skills_list}

Respond with ONLY the skill name (e.g., "analyze_project", "system_diagnostics")."""

        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM
        skill_text = await _call_ollama_llm(messages, temperature=0.2)
        
        # Clean and validate skill
        selected_skill_name = skill_text.strip().lower().replace(" ", "_")
        
        # Validate against available skills
        selected_skill = None
        for skill in domain_skills:
            if skill.name.lower() == selected_skill_name or skill.name == selected_skill_name:
                selected_skill = skill
                break
        
        if not selected_skill:
            logger.warning(f"LLM selected skill '{selected_skill_name}' not found, using first available")
            selected_skill = domain_skills[0]
        
        state["selected_skill"] = selected_skill.name
        state["metadata"]["skill_selection"] = {
            "selected_skill": selected_skill.name,
            "skill_description": selected_skill.description,
            "required_tools": selected_skill.required_tools,
            "selection_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Skill selected as '{selected_skill.name}' for user {state['user_id']}")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in select_skill: {e}")
        add_error(state, f"Skill selection failed: {str(e)}")
        return state


async def create_execution_plan(state: AntigenTaskState) -> AntigenTaskState:
    """Create a structured execution plan for the task using the selected skill.
    
    This node generates a multi-step plan based on the skill's instructions
    and the specific task requirements.
    
    Phase B2: LLM-powered execution plan generation.
    
    Args:
        state: Current task state with selected_skill
    
    Returns:
        Updated task state with execution plan
    """
    logger.info(f"Creating execution plan for skill '{state['selected_skill']}'")
    
    try:
        from .capability_system import skill_registry
        
        skill = skill_registry.get(state['selected_skill'])
        
        if not skill:
            state["plan"] = None
            add_error(state, f"Skill '{state['selected_skill']}' not found")
            return state
        
        # Build plan generation prompt
        prompt = f"""Create a detailed execution plan for the following task:

Task: {state['user_request']}
Domain: {state['selected_domain']}
Skill: {skill.name}
Skill Instructions: {skill.instructions}
Required Tools: {', '.join(skill.required_tools)}

Generate a step-by-step plan in JSON format:
{{
  "steps": [
    {{
      "step_number": 1,
      "description": "what this step accomplishes",
      "tool": "tool_name to use",
      "inputs": {{"param": "value"}},
      "expected_output": "what to expect from this step"
    }}
  ],
  "estimated_complexity": "low|medium|high",
  "requires_confirmation": false
}}

Output ONLY valid JSON, no markdown, no explanation."""

        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM
        plan_text = await _call_ollama_llm(messages, temperature=0.5)
        
        # Parse JSON response
        try:
            plan_text = plan_text.strip()
            if plan_text.startswith("```"):
                plan_text = plan_text.strip("`")
                if plan_text.lower().startswith("json"):
                    plan_text = plan_text[4:]
                plan_text = plan_text.strip()
            
            plan = json.loads(plan_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}, creating fallback plan")
            # Create simple fallback plan
            plan = {
                "steps": [
                    {
                        "step_number": 1,
                        "description": f"Execute {skill.name}",
                        "tool": skill.required_tools[0] if skill.required_tools else "generic",
                        "inputs": {"task": state['user_request']},
                        "expected_output": "Task completion result"
                    }
                ],
                "estimated_complexity": "medium",
                "requires_confirmation": False
            }
        
        state["plan"] = plan
        state["metadata"]["plan_generation"] = {
            "plan_created": True,
            "number_of_steps": len(plan.get("steps", [])),
            "complexity": plan.get("estimated_complexity", "medium"),
            "generation_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Execution plan created with {len(plan.get('steps', []))} steps for user {state['user_id']}")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in create_execution_plan: {e}")
        add_error(state, f"Execution plan creation failed: {str(e)}")
        return state


# ---------------------------------------------------------------------------
# Phase B3: Tool Selection and Permission Validation Nodes
# ---------------------------------------------------------------------------

async def select_tools(state: AntigenTaskState) -> AntigenTaskState:
    """Select appropriate tools for each step in the execution plan.
    
    This node:
    - Reads the execution plan from B2
    - Validates each step's requested tool against the Tool Registry
    - Ensures tools exist and are compatible
    - Maps tools to plan steps
    - Never allows LLM to invent executable tools
    
    Phase B3: Tool selection with Tool Registry validation.
    
    Args:
        state: Current task state with execution plan
    
    Returns:
        Updated task state with selected tools and validation results
    """
    logger.info(f"Selecting tools for user {state['user_id']}")
    
    try:
        from .capability_system import tool_registry
        
        # Initialize tool selection fields
        state["selected_tools"] = {}
        state["unavailable_tools"] = []
        state["tool_validation_errors"] = []
        
        # Check if we have a plan
        if not state.get("plan") or not state["plan"].get("steps"):
            state["tool_validation_errors"].append("No execution plan or steps available for tool selection")
            return state
        
        plan_steps = state["plan"]["steps"]
        
        for step in plan_steps:
            step_number = step.get("step_number")
            requested_tool_name = step.get("tool")
            
            if not requested_tool_name:
                state["tool_validation_errors"].append(f"Step {step_number}: No tool specified")
                continue
            
            # Validate tool exists in registry
            tool = tool_registry.get(requested_tool_name)
            
            if not tool:
                state["unavailable_tools"].append(requested_tool_name)
                state["tool_validation_errors"].append(f"Step {step_number}: Tool '{requested_tool_name}' not found in Tool Registry")
                continue
            
            # Tool exists and is available
            state["selected_tools"][str(step_number)] = {
                "tool_name": tool.name,
                "tool_description": tool.description,
                "permission_level": tool.permission_level.value,
                "domain": tool.domain,
                "category": tool.category,
                "has_handler": tool.execution_handler is not None
            }
            
            logger.info(f"Step {step_number}: Selected tool '{tool.name}' (permission: {tool.permission_level.value})")
        
        # Store tool selection results in metadata
        state["tool_selection_results"] = {
            "total_steps": len(plan_steps),
            "tools_selected": len(state["selected_tools"]),
            "tools_unavailable": len(state["unavailable_tools"]),
            "validation_errors": len(state["tool_validation_errors"]),
            "selection_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Tool selection complete: {len(state['selected_tools'])} tools selected, {len(state['unavailable_tools'])} unavailable")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in select_tools: {e}")
        add_error(state, f"Tool selection failed: {str(e)}")
        return state


async def validate_permissions(state: AntigenTaskState) -> AntigenTaskState:
    """Validate permissions for all selected tools.
    
    This node:
    - Checks permission requirements for each selected tool
    - Identifies blocked operations
    - Identifies operations requiring confirmation
    - Uses existing capability permission system
    - Never bypasses permission requirements
    
    Phase B3: Permission validation using existing PermissionLevel system.
    
    Args:
        state: Current task state with selected tools
    
    Returns:
        Updated task state with permission validation results
    """
    logger.info(f"Validating permissions for user {state['user_id']}")
    
    try:
        from .capability_system import PermissionLevel
        
        # Initialize permission validation fields
        state["permission_requirements"] = {}
        state["permission_results"] = {}
        state["blocked_operations"] = []
        state["confirmation_requirements"] = []
        
        # Check if we have selected tools
        if not state.get("selected_tools"):
            state["tool_validation_errors"].append("No tools selected for permission validation")
            return state
        
        # Default user permission level (this could be enhanced to fetch from user context)
        user_permission_level = PermissionLevel.SAFE_ACTION
        
        for step_number, tool_info in state["selected_tools"].items():
            tool_name = tool_info["tool_name"]
            tool_permission_str = tool_info["permission_level"]
            
            try:
                tool_permission = PermissionLevel(tool_permission_str)
            except ValueError:
                state["tool_validation_errors"].append(f"Step {step_number}: Invalid permission level '{tool_permission_str}'")
                continue
            
            # Store permission requirement
            state["permission_requirements"][step_number] = {
                "tool_name": tool_name,
                "required_permission": tool_permission_str,
                "step_number": step_number
            }
            
            # Check if operation is allowed
            permission_hierarchy = {
                PermissionLevel.READ_ONLY: 0,
                PermissionLevel.SAFE_ACTION: 1,
                PermissionLevel.REQUIRES_CONFIRMATION: 2,
                PermissionLevel.RESTRICTED: 3
            }
            
            user_level = permission_hierarchy.get(user_permission_level, 0)
            tool_level = permission_hierarchy.get(tool_permission, 0)
            
            if user_level < tool_level:
                # Permission denied
                if tool_permission == PermissionLevel.RESTRICTED:
                    state["blocked_operations"].append(f"Step {step_number}: {tool_name} (RESTRICTED)")
                    state["permission_results"][step_number] = {
                        "allowed": False,
                        "reason": "User permission level insufficient for RESTRICTED operation",
                        "required": tool_permission_str,
                        "action": "blocked"
                    }
                elif tool_permission == PermissionLevel.REQUIRES_CONFIRMATION:
                    state["confirmation_requirements"].append(f"Step {step_number}: {tool_name} (REQUIRES_CONFIRMATION)")
                    state["permission_results"][step_number] = {
                        "allowed": False,
                        "reason": "Operation requires user confirmation",
                        "required": tool_permission_str,
                        "action": "confirmation_required"
                    }
                else:
                    state["blocked_operations"].append(f"Step {step_number}: {tool_name} ({tool_permission_str})")
                    state["permission_results"][step_number] = {
                        "allowed": False,
                        "reason": f"User permission level insufficient for {tool_permission_str}",
                        "required": tool_permission_str,
                        "action": "blocked"
                    }
            else:
                # Permission granted
                state["permission_results"][step_number] = {
                    "allowed": True,
                    "reason": "User permission level sufficient",
                    "required": tool_permission_str,
                    "action": "allowed"
                }
            
            logger.info(f"Step {step_number}: Tool '{tool_name}' permission {tool_permission_str} - {'allowed' if user_level >= tool_level else 'denied'}")
        
        # Store permission validation summary in metadata
        state["metadata"]["permission_validation"] = {
            "total_tools_checked": len(state["selected_tools"]),
            "tools_allowed": len([r for r in state["permission_results"].values() if r.get("allowed")]),
            "tools_blocked": len(state["blocked_operations"]),
            "tools_require_confirmation": len(state["confirmation_requirements"]),
            "validation_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Permission validation complete: {len(state['blocked_operations'])} blocked, {len(state['confirmation_requirements'])} require confirmation")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in validate_permissions: {e}")
        add_error(state, f"Permission validation failed: {str(e)}")
        return state


# ---------------------------------------------------------------------------
# Phase B4: Execution and Result Collection Nodes
# ---------------------------------------------------------------------------

async def execute_plan(state: AntigenTaskState) -> AntigenTaskState:
    """Execute the validated execution plan using selected tools.
    
    This node:
    - Executes plan steps sequentially
    - Uses only validated tools from Tool Registry
    - Enforces permission checks before each execution
    - Captures execution results and errors
    - Handles confirmation-required operations
    - Never bypasses permission validation
    
    Phase B4: Controlled sequential execution with permission enforcement.
    
    Args:
        state: Current task state with selected tools and permission results
    
    Returns:
        Updated task state with execution results
    """
    logger.info(f"Executing plan for user {state['user_id']}")
    
    try:
        from .capability_system import tool_registry
        
        # Initialize execution state
        state["execution_state"] = "running"
        state["step_execution_states"] = {}
        state["current_step"] = 0
        
        # Check if we have tools to execute
        if not state.get("selected_tools"):
            state["execution_state"] = "failed"
            add_error(state, "No tools selected for execution")
            return update_state_status(state, TaskStatus.FAILED)
        
        # Check if we have blocked operations
        if state.get("blocked_operations"):
            state["execution_state"] = "blocked"
            add_error(state, f"Execution blocked: {len(state['blocked_operations'])} operations require higher permissions")
            return update_state_status(state, TaskStatus.FAILED)
        
        # Execute each step sequentially
        plan_steps = state.get("plan", {}).get("steps", [])
        
        for step in plan_steps:
            step_number = step.get("step_number")
            state["current_step"] = step_number
            
            # Get selected tool for this step
            step_key = str(step_number)
            if step_key not in state["selected_tools"]:
                state["step_execution_states"][step_key] = "failed"
                state["execution_results"].append({
                    "step_number": step_number,
                    "status": "failed",
                    "error": f"No tool selected for step {step_number}"
                })
                continue
            
            tool_info = state["selected_tools"][step_key]
            tool_name = tool_info["tool_name"]
            
            # Check permission before execution
            perm_result = state.get("permission_results", {}).get(step_key, {})
            if not perm_result.get("allowed", False):
                action = perm_result.get("action", "blocked")
                state["step_execution_states"][step_key] = action
                state["execution_results"].append({
                    "step_number": step_number,
                    "tool_name": tool_name,
                    "status": action,
                    "error": f"Operation not allowed: {perm_result.get('reason', 'Permission denied')}"
                })
                continue
            
            # Get the tool from registry
            tool = tool_registry.get(tool_name)
            if not tool or not tool.execution_handler:
                state["step_execution_states"][step_key] = "failed"
                state["execution_results"].append({
                    "step_number": step_number,
                    "tool_name": tool_name,
                    "status": "failed",
                    "error": f"Tool '{tool_name}' has no execution handler"
                })
                continue
            
            # Execute the tool
            try:
                logger.info(f"Executing step {step_number} with tool '{tool_name}'")
                
                # Prepare input data
                input_data = step.get("inputs", {})
                
                # Call the tool's execution handler
                result_data = tool.execution_handler(input_data)
                
                # Store successful result
                state["step_execution_states"][step_key] = "completed"
                state["execution_results"].append({
                    "step_number": step_number,
                    "tool_name": tool_name,
                    "status": "completed",
                    "output": result_data,
                    "error": None
                })
                
                logger.info(f"Step {step_number} completed successfully")
                
            except Exception as e:
                logger.exception(f"Error executing step {step_number} with tool '{tool_name}'")
                state["step_execution_states"][step_key] = "failed"
                state["execution_results"].append({
                    "step_number": step_number,
                    "tool_name": tool_name,
                    "status": "failed",
                    "error": str(e),
                    "output": None
                })
        
        # Determine overall execution state
        completed_steps = len([s for s in state["step_execution_states"].values() if s == "completed"])
        failed_steps = len([s for s in state["step_execution_states"].values() if s == "failed"])
        total_steps = len(state["step_execution_states"])
        
        if failed_steps == 0 and completed_steps == total_steps:
            state["execution_state"] = "completed"
            state["status"] = TaskStatus.COMPLETED
        elif failed_steps > 0:
            state["execution_state"] = "partial_failure"
            state["status"] = TaskStatus.FAILED
        else:
            state["execution_state"] = "no_execution"
            state["status"] = TaskStatus.FAILED
        
        # Store execution summary in metadata
        state["metadata"]["execution_summary"] = {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "execution_state": state["execution_state"],
            "execution_timestamp": state["updated_at"].isoformat()
        }
        
        logger.info(f"Plan execution complete: {completed_steps}/{total_steps} steps completed, {failed_steps} failed")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in execute_plan: {e}")
        state["execution_state"] = "error"
        add_error(state, f"Plan execution failed: {str(e)}")
        return update_state_status(state, TaskStatus.FAILED)


async def collect_results(state: AntigenTaskState) -> AntigenTaskState:
    """Collect and format execution results for the final response.
    
    This node:
    - Compiles execution results into a structured format
    - Generates a summary of the task execution
    - Prepares the final result for the user
    - Handles both successful and failed executions
    
    Phase B4: Result collection and formatting.
    
    Args:
        state: Current task state with execution results
    
    Returns:
        Updated task state with final result
    """
    logger.info(f"Collecting results for user {state['user_id']}")
    
    try:
        # Compile final result
        final_result = {
            "task": state["user_request"],
            "domain": state.get("selected_domain"),
            "skill": state.get("selected_skill"),
            "execution_state": state.get("execution_state", "unknown"),
            "steps_completed": len([r for r in state.get("execution_results", []) if r.get("status") == "completed"]),
            "steps_failed": len([r for r in state.get("execution_results", []) if r.get("status") == "failed"]),
            "total_steps": len(state.get("execution_results", [])),
            "execution_results": state.get("execution_results", []),
            "tool_selection": {
                "tools_selected": len(state.get("selected_tools", {})),
                "tools_unavailable": len(state.get("unavailable_tools", [])),
                "validation_errors": state.get("tool_validation_errors", [])
            },
            "permission_validation": {
                "tools_allowed": len([r for r in state.get("permission_results", {}).values() if r.get("allowed")]),
                "tools_blocked": len(state.get("blocked_operations", [])),
                "tools_require_confirmation": len(state.get("confirmation_requirements", []))
            }
        }
        
        # Add execution details if available
        if state.get("execution_results"):
            successful_results = [r for r in state["execution_results"] if r.get("status") == "completed"]
            if successful_results:
                final_result["successful_outputs"] = [r.get("output") for r in successful_results]
        
        state["final_result"] = final_result
        
        logger.info(f"Results collection complete: {final_result['execution_state']}")
        
        return state
        
    except Exception as e:
        logger.exception(f"Error in collect_results: {e}")
        add_error(state, f"Result collection failed: {str(e)}")
        return state


# Future nodes to be implemented in later phases:
# def verify_results(state: AntigenTaskState) -> AntigenTaskState:
#     """Phase B5: Verify execution results against original intent"""
#     pass

# def recover_from_error(state: AntigenTaskState) -> AntigenTaskState:
#     """Phase B5: Analyze errors and generate recovery strategies"""
#     pass

# def learn_from_execution(state: AntigenTaskState) -> AntigenTaskState:
#     """Phase B6: Store successful patterns in memory service"""
#     pass