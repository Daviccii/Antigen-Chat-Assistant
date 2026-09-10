"""Cybersecurity domain tools: dependency vulnerability scanning, static
code security review, and local listening-port visibility. All READ_ONLY
— every one of these reads/reports, none of them modify anything or act
on another host.

scan_dependencies and analyze_code_security take a `path` — path safety
is enforced upstream by the Security Gateway (gated_execution.py checks
check_path_allowed() before calling into these handlers at all), so
these handlers can trust the path they're given.
"""
import logging
from typing import Dict, Any

from .capability_system import Tool, ToolInputSchema, ToolOutputSchema, PermissionLevel, tool_registry
from . import cybersecurity_scan_deps as scan_deps
from . import cybersecurity_static_scan as static_scan
from . import cybersecurity_network as network

logger = logging.getLogger(__name__)


def scan_dependencies_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    ecosystem = input_data.get("ecosystem")
    manifest_content = input_data.get("manifest_content")
    path = input_data.get("path")

    if not ecosystem:
        return {"error": "ecosystem ('pypi' or 'npm') is required"}
    if not manifest_content and not path:
        return {"error": "provide either manifest_content (pasted file contents) or path"}

    try:
        if not manifest_content:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                manifest_content = f.read()
        return scan_deps.scan_manifest(manifest_content, ecosystem)
    except scan_deps.ManifestParseError as e:
        return {"error": str(e)}
    except OSError as e:
        return {"error": f"Could not read file: {e}"}
    except Exception as e:
        logger.exception("Error scanning dependencies")
        return {"error": f"Scan failed: {e}"}


def analyze_code_security_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    path = input_data.get("path")
    if not path:
        return {"error": "path is required"}
    try:
        return static_scan.analyze_path(path)
    except Exception as e:
        logger.exception(f"Error analyzing code security at {path}")
        return {"error": f"Scan failed: {e}"}


def get_listening_ports_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return network.get_listening_ports()
    except Exception as e:
        logger.exception("Error getting listening ports")
        return {"error": str(e)}


scan_dependencies_tool = Tool(
    name="scan_dependencies",
    description="Check a requirements.txt or package.json's pinned packages against the OSV.dev vulnerability database",
    input_schema={
        "ecosystem": ToolInputSchema(type="string", description="'pypi' or 'npm'", required=True),
        "manifest_content": ToolInputSchema(type="string", description="Raw file contents, if not reading from disk", required=False),
        "path": ToolInputSchema(type="string", description="Path to requirements.txt / package.json, if reading from disk", required=False),
    },
    output_schema=ToolOutputSchema(type="object", description="Vulnerable packages found, with CVE/GHSA IDs and severity"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="cybersecurity",
    category="dependency_scan",
    execution_handler=scan_dependencies_handler,
)

analyze_code_security_tool = Tool(
    name="analyze_code_security",
    description="Static security scan of a file or directory: hardcoded secrets, shell injection risk, insecure deserialization, weak crypto",
    input_schema={
        "path": ToolInputSchema(type="string", description="File or directory to scan", required=True),
    },
    output_schema=ToolOutputSchema(type="object", description="Findings with file/line/severity/category/description, sorted by severity"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="cybersecurity",
    category="static_analysis",
    execution_handler=analyze_code_security_handler,
)

get_listening_ports_tool = Tool(
    name="get_listening_ports",
    description="List ports currently listening on this machine and which process owns each one (localhost only, never scans other hosts)",
    input_schema={},
    output_schema=ToolOutputSchema(type="object", description="Listening ports with address, pid, and process name"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="cybersecurity",
    category="network_visibility",
    execution_handler=get_listening_ports_handler,
)

tool_registry.register(scan_dependencies_tool)
tool_registry.register(analyze_code_security_tool)
tool_registry.register(get_listening_ports_tool)