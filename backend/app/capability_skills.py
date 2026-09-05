"""Basic Skills for Capability System.

This module provides foundational skills that demonstrate the capability architecture.
These skills use the registered tools to accomplish specific types of tasks.
"""
from typing import Dict, Any
import logging

from .capability_system import (
    Skill, skill_registry, PermissionLevel
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Software Engineering Skills
# ---------------------------------------------------------------------------

# Software Engineering: Project Analysis Skill
project_analysis_skill = Skill(
    name="analyze_project",
    description="Analyze a software project structure and detect its type, organization, and key components",
    domain="software_engineering",
    required_tools=["analyze_project_structure", "list_directory", "read_file"],
    capabilities=[
        "Detect project type (Python, Node.js, etc.)",
        "Identify project structure and organization",
        "List key project files and directories",
        "Provide basic project insights"
    ],
    instructions="""To analyze a project:
1. Use analyze_project_structure to detect project type
2. Use list_directory to explore the main directory structure
3. Use read_file to examine key configuration files if needed
4. Summarize findings about the project's type, structure, and organization""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.READ_ONLY
)

# Software Engineering: File Exploration Skill
file_exploration_skill = Skill(
    name="explore_files",
    description="Explore and understand the file structure of a directory or project",
    domain="software_engineering",
    required_tools=["list_directory", "read_file"],
    capabilities=[
        "List directory contents",
        "Read file contents",
        "Navigate directory structures",
        "Understand file organization"
    ],
    instructions="""To explore files:
1. Use list_directory to see what's in a directory
2. Use read_file to examine specific files of interest
3. Navigate to subdirectories by updating the path parameter
4. Report back the structure and key findings""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.READ_ONLY
)


# ---------------------------------------------------------------------------
# System Diagnostics Skills
# ---------------------------------------------------------------------------

# System: Basic Diagnostics Skill
system_diagnostics_skill = Skill(
    name="system_diagnostics",
    description="Run basic system diagnostics to check system health and status",
    domain="system",
    required_tools=["get_system_info", "get_disk_usage"],
    capabilities=[
        "Get system information",
        "Check disk usage",
        "Provide basic system health status",
        "Report system configuration"
    ],
    instructions="""To run system diagnostics:
1. Use get_system_info to gather basic system information
2. Use get_disk_usage to check disk space
3. Analyze the results and provide a health summary
4. Report any issues or concerns""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.READ_ONLY
)


# ---------------------------------------------------------------------------
# IT Skills
# ---------------------------------------------------------------------------

# IT: System Information Skill
system_info_skill = Skill(
    name="get_system_information",
    description="Get comprehensive system information including OS, hardware, and configuration",
    domain="it",
    required_tools=["get_system_info", "get_disk_usage", "get_current_time"],
    capabilities=[
        "Retrieve operating system information",
        "Check disk space and usage",
        "Get current time context",
        "Provide system overview"
    ],
    instructions="""To get system information:
1. Use get_system_info to gather OS and hardware details
2. Use get_disk_usage to check storage status
3. Use get_current_time to provide time context
4. Compile information into a comprehensive system overview""",
    execution_strategy="sequential",
    permission_level=PermissionLevel.READ_ONLY
)


# ---------------------------------------------------------------------------
# Register all skills
# ---------------------------------------------------------------------------

skill_registry.register(project_analysis_skill)
skill_registry.register(file_exploration_skill)
skill_registry.register(system_diagnostics_skill)
skill_registry.register(system_info_skill)


# ---------------------------------------------------------------------------
# Domain initialization
# ---------------------------------------------------------------------------

def initialize_basic_domains():
    """Initialize basic domains with their skills and tools."""
    from .capability_system import capability_config
    
    # Enable basic domains
    capability_config.enable_domain("software_engineering")
    capability_config.enable_domain("system")
    capability_config.enable_domain("it")
    
    logger.info("Initialized basic capability domains: software_engineering, system, it")


# Auto-initialize on module import
initialize_basic_domains()