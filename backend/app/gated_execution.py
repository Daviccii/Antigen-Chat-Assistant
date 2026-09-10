"""The one function in the codebase allowed to call tool.execution_handler.

Before Phase D2, four different places called that directly: the manual
/tools/{name}/execute endpoint, TaskOrchestrator.execute_step, and two
spots in langgraph_nodes.py (the execution node and the recovery/retry
node). Each one now goes through execute_tool_gated() instead, so there
is exactly one place that decides "does this tool actually get to run,"
and exactly one place that can drift out of sync with the gateway.
"""
import time
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from .capability_system import Tool, ExecutionResult
from .security_gateway import check_permission, check_path_allowed
from .security_models import GatewayDecision

logger = logging.getLogger(__name__)


def execute_tool_gated(db: Session, user_id: int, tool: Tool, input_data: Dict[str, Any]) -> ExecutionResult:
    """Runs a tool's execution_handler only if the Security Gateway
    approves it. check_permission() writes an audit row for every call
    here regardless of outcome — allowed, blocked, or needs-confirmation
    all get logged, not just the denials.
    """
    if not tool.execution_handler:
        return ExecutionResult(success=False, error=f"Tool '{tool.name}' has no execution handler")

    target_path = input_data.get("path") if isinstance(input_data, dict) else None

    gateway_result = check_permission(
        db=db,
        user_id=user_id,
        tool_name=tool.name,
        domain=tool.domain,
        permission_level=tool.permission_level,
        input_summary=str(input_data)[:500],
        target_path=target_path,
    )

    if gateway_result.decision == GatewayDecision.BLOCKED:
        logger.info(f"Gateway blocked '{tool.name}' for user {user_id}: {gateway_result.reason}")
        return ExecutionResult(success=False, error=f"Blocked by Security Gateway: {gateway_result.reason}")

    if gateway_result.decision == GatewayDecision.NEEDS_CONFIRMATION:
        # No confirmation UI/flow exists yet — fail closed rather than
        # silently auto-approving a MODIFY/DESTRUCTIVE/ADMIN operation.
        # This becomes an actual prompt-and-wait flow in a later phase.
        return ExecutionResult(
            success=False,
            error=f"This action needs your confirmation before it can run: {gateway_result.reason}",
            metadata={"needs_confirmation": True},
        )

    # ALLOWED at the tier/category level. Any tool that takes a `path`
    # still needs allowed-areas enforcement — this used to only fire for
    # domain == "file_system", which meant a new domain with a path-taking
    # tool (like cybersecurity's scan_dependencies/analyze_code_security)
    # would have silently skipped path validation. Now it's unconditional
    # on the presence of a path, not the domain name.
    if target_path:
        path_ok, path_reason = check_path_allowed(db, user_id, target_path)
        if not path_ok:
            logger.info(f"Gateway blocked '{tool.name}' on path '{target_path}': {path_reason}")
            return ExecutionResult(success=False, error=f"Blocked by Security Gateway (path): {path_reason}")

    start = time.time()
    try:
        result_data = tool.execution_handler(input_data)
        elapsed_ms = (time.time() - start) * 1000
        return ExecutionResult(success=True, data=result_data, execution_time_ms=elapsed_ms)
    except Exception as e:
        logger.exception(f"Error executing gated tool '{tool.name}'")
        return ExecutionResult(success=False, error=str(e))