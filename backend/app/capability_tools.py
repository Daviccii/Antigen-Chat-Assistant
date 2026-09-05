"""Basic Tools for Capability System.

This module provides foundational tools that demonstrate the capability architecture.
These are safe, read-only or safe-action tools that can be used as examples.
"""
import os
import subprocess
from typing import Dict, Any
from datetime import datetime
import logging

from .capability_system import (
    Tool, ToolInputSchema, ToolOutputSchema, PermissionLevel, tool_registry
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File System Tools
# ---------------------------------------------------------------------------

def list_directory_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for listing directory contents."""
    path = input_data.get("path", ".")
    
    try:
        if not os.path.exists(path):
            return {"error": f"Path does not exist: {path}"}
        
        if not os.path.isdir(path):
            return {"error": f"Path is not a directory: {path}"}
        
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            items.append({
                "name": item,
                "type": "directory" if os.path.isdir(item_path) else "file",
                "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
            })
        
        return {"path": path, "items": items, "count": len(items)}
    
    except Exception as e:
        logger.exception(f"Error listing directory {path}")
        return {"error": str(e)}


def read_file_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for reading file contents."""
    path = input_data.get("path")
    max_lines = input_data.get("max_lines", 100)
    
    if not path:
        return {"error": "Path is required"}
    
    try:
        if not os.path.exists(path):
            return {"error": f"File does not exist: {path}"}
        
        if not os.path.isfile(path):
            return {"error": f"Path is not a file: {path}"}
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip('\n'))
        
        return {
            "path": path,
            "lines": lines,
            "total_lines_read": len(lines),
            "truncated": len(lines) == max_lines
        }
    
    except Exception as e:
        logger.exception(f"Error reading file {path}")
        return {"error": str(e)}


# Register file system tools
list_directory_tool = Tool(
    name="list_directory",
    description="List contents of a directory",
    input_schema={
        "path": ToolInputSchema(type="string", description="Directory path to list", required=False, default="."),
        "max_items": ToolInputSchema(type="integer", description="Maximum number of items to return", required=False, default=100)
    },
    output_schema=ToolOutputSchema(type="object", description="Directory listing with file names and types"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="file_system",
    category="exploration",
    execution_handler=list_directory_handler
)

read_file_tool = Tool(
    name="read_file",
    description="Read contents of a text file",
    input_schema={
        "path": ToolInputSchema(type="string", description="File path to read", required=True),
        "max_lines": ToolInputSchema(type="integer", description="Maximum number of lines to read", required=False, default=100)
    },
    output_schema=ToolOutputSchema(type="object", description="File contents as lines of text"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="file_system",
    category="exploration",
    execution_handler=read_file_handler
)

tool_registry.register(list_directory_tool)
tool_registry.register(read_file_tool)


# ---------------------------------------------------------------------------
# System Information Tools
# ---------------------------------------------------------------------------

def get_system_info_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for getting basic system information."""
    try:
        import platform
        
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.exception("Error getting system info")
        return {"error": str(e)}


def get_disk_usage_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for getting disk usage information."""
    path = input_data.get("path", ".")
    
    try:
        import shutil
        
        usage = shutil.disk_usage(path)
        
        return {
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 2)
        }
    except Exception as e:
        logger.exception(f"Error getting disk usage for {path}")
        return {"error": str(e)}


# Register system information tools
get_system_info_tool = Tool(
    name="get_system_info",
    description="Get basic system information",
    input_schema={},
    output_schema=ToolOutputSchema(type="object", description="System information including OS, Python version, etc."),
    permission_level=PermissionLevel.READ_ONLY,
    domain="system",
    category="diagnostics",
    execution_handler=get_system_info_handler
)

get_disk_usage_tool = Tool(
    name="get_disk_usage",
    description="Get disk usage information for a path",
    input_schema={
        "path": ToolInputSchema(type="string", description="Path to check disk usage for", required=False, default=".")
    },
    output_schema=ToolOutputSchema(type="object", description="Disk usage statistics"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="system",
    category="diagnostics",
    execution_handler=get_disk_usage_handler
)

tool_registry.register(get_system_info_tool)
tool_registry.register(get_disk_usage_tool)


# ---------------------------------------------------------------------------
# Project Analysis Tools (Integration with existing Antigen systems)
# ---------------------------------------------------------------------------

def analyze_project_structure_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for analyzing project structure."""
    path = input_data.get("path", ".")
    
    try:
        # Look for common project files
        project_indicators = {
            "package.json": "Node.js/JavaScript project",
            "requirements.txt": "Python project",
            "Cargo.toml": "Rust project",
            "go.mod": "Go project",
            "pom.xml": "Maven/Java project",
            "build.gradle": "Gradle/Java project",
            "Gemfile": "Ruby project",
            "composer.json": "PHP project",
            "Dockerfile": "Docker project",
            "docker-compose.yml": "Docker Compose project"
        }
        
        detected_projects = []
        for filename, description in project_indicators.items():
            file_path = os.path.join(path, filename)
            if os.path.exists(file_path):
                detected_projects.append({
                    "file": filename,
                    "type": description
                })
        
        # Count common directories
        common_dirs = ["src", "lib", "test", "tests", "docs", "build", "dist"]
        found_dirs = []
        for dirname in common_dirs:
            dir_path = os.path.join(path, dirname)
            if os.path.isdir(dir_path):
                found_dirs.append(dirname)
        
        return {
            "path": path,
            "detected_projects": detected_projects,
            "common_directories": found_dirs,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.exception(f"Error analyzing project structure at {path}")
        return {"error": str(e)}


# Register project analysis tool
analyze_project_structure_tool = Tool(
    name="analyze_project_structure",
    description="Analyze project structure to detect project type and organization",
    input_schema={
        "path": ToolInputSchema(type="string", description="Project path to analyze", required=False, default=".")
    },
    output_schema=ToolOutputSchema(type="object", description="Project structure analysis"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="software_engineering",
    category="analysis",
    execution_handler=analyze_project_structure_handler
)

tool_registry.register(analyze_project_structure_tool)


# ---------------------------------------------------------------------------
# Time and Date Tools (Integration with existing TimeService)
# ---------------------------------------------------------------------------

def get_current_time_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for getting current time context."""
    try:
        from .time_service import TimeService
        
        timezone = input_data.get("timezone", "Africa/Nairobi")
        time_context = TimeService.get_time_context(timezone)
        
        return time_context
    except Exception as e:
        logger.exception("Error getting current time")
        return {"error": str(e)}


# Register time tool
get_current_time_tool = Tool(
    name="get_current_time",
    description="Get current time context for a specific timezone",
    input_schema={
        "timezone": ToolInputSchema(type="string", description="Timezone string (e.g., 'Africa/Nairobi')", required=False, default="Africa/Nairobi")
    },
    output_schema=ToolOutputSchema(type="object", description="Current time context"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="system",
    category="time",
    execution_handler=get_current_time_handler
)

tool_registry.register(get_current_time_tool)