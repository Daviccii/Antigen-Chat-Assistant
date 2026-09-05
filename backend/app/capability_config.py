"""Capability Configuration System.

This module provides configuration management for the capability system,
allowing easy registration of new tools and skills without modifying core code.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .capability_system import (
    Tool, Skill, PermissionLevel,
    tool_registry, skill_registry, capability_config
)

logger = logging.getLogger(__name__)


@dataclass
class ToolConfig:
    """Configuration for a tool."""
    name: str
    description: str
    input_schema: Dict[str, Dict[str, Any]]
    output_schema: Dict[str, str]
    permission_level: str = "SAFE_ACTION"
    domain: Optional[str] = None
    category: Optional[str] = None
    module_path: Optional[str] = None  # Python module path for execution handler


@dataclass
class SkillConfig:
    """Configuration for a skill."""
    name: str
    description: str
    domain: str
    required_tools: List[str]
    capabilities: List[str]
    instructions: str
    execution_strategy: str = "sequential"
    permission_level: str = "SAFE_ACTION"


@dataclass
class DomainConfig:
    """Configuration for a domain."""
    name: str
    description: str
    enabled: bool = True
    tools: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)


class CapabilityConfigManager:
    """Manages capability configuration from files and programmatic registration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "capability_config.json"
        self.tool_configs: Dict[str, ToolConfig] = {}
        self.skill_configs: Dict[str, SkillConfig] = {}
        self.domain_configs: Dict[str, DomainConfig] = {}
    
    def load_from_file(self) -> None:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            logger.info(f"Capability config file not found at {self.config_path}, using defaults")
            return
        
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load tool configurations
            for tool_name, tool_data in config_data.get("tools", {}).items():
                self.tool_configs[tool_name] = ToolConfig(**tool_data)
            
            # Load skill configurations
            for skill_name, skill_data in config_data.get("skills", {}).items():
                self.skill_configs[skill_name] = SkillConfig(**skill_data)
            
            # Load domain configurations
            for domain_name, domain_data in config_data.get("domains", {}).items():
                self.domain_configs[domain_name] = DomainConfig(**domain_data)
            
            logger.info(f"Loaded capability configuration from {self.config_path}")
        
        except Exception as e:
            logger.exception(f"Error loading capability configuration from {self.config_path}")
    
    def save_to_file(self) -> None:
        """Save current configuration to JSON file."""
        try:
            config_data = {
                "tools": {
                    name: {
                        "name": config.name,
                        "description": config.description,
                        "input_schema": config.input_schema,
                        "output_schema": config.output_schema,
                        "permission_level": config.permission_level,
                        "domain": config.domain,
                        "category": config.category,
                        "module_path": config.module_path
                    }
                    for name, config in self.tool_configs.items()
                },
                "skills": {
                    name: {
                        "name": config.name,
                        "description": config.description,
                        "domain": config.domain,
                        "required_tools": config.required_tools,
                        "capabilities": config.capabilities,
                        "instructions": config.instructions,
                        "execution_strategy": config.execution_strategy,
                        "permission_level": config.permission_level
                    }
                    for name, config in self.skill_configs.items()
                },
                "domains": {
                    name: {
                        "name": config.name,
                        "description": config.description,
                        "enabled": config.enabled,
                        "tools": config.tools,
                        "skills": config.skills
                    }
                    for name, config in self.domain_configs.items()
                }
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved capability configuration to {self.config_path}")
        
        except Exception as e:
            logger.exception(f"Error saving capability configuration to {self.config_path}")
    
    def register_tool_config(self, config: ToolConfig) -> None:
        """Register a tool configuration."""
        self.tool_configs[config.name] = config
        logger.info(f"Registered tool configuration: {config.name}")
    
    def register_skill_config(self, config: SkillConfig) -> None:
        """Register a skill configuration."""
        self.skill_configs[config.name] = config
        logger.info(f"Registered skill configuration: {config.name}")
    
    def register_domain_config(self, config: DomainConfig) -> None:
        """Register a domain configuration."""
        self.domain_configs[config.name] = config
        logger.info(f"Registered domain configuration: {config.name}")
    
    def apply_configurations(self) -> None:
        """Apply loaded configurations to the registries."""
        # Apply domain configurations
        for domain_name, domain_config in self.domain_configs.items():
            if domain_config.enabled:
                capability_config.enable_domain(domain_name)
                logger.info(f"Enabled domain: {domain_name}")
        
        # Note: Tool and skill registration requires execution handlers
        # which need to be implemented in Python code. This configuration
        # system is primarily for metadata and enabling/disabling capabilities.
        logger.info("Applied capability configurations")


# Global configuration manager instance
config_manager = CapabilityConfigManager()


def register_tool_from_config(config: ToolConfig, execution_handler=None) -> Tool:
    """Create and register a Tool from configuration.
    
    Args:
        config: ToolConfig instance
        execution_handler: Optional callable that handles tool execution
    
    Returns:
        The registered Tool instance
    """
    from .capability_system import ToolInputSchema, ToolOutputSchema
    
    # Convert input schema dict to ToolInputSchema objects
    input_schema = {
        key: ToolInputSchema(
            type=value.get("type", "string"),
            description=value.get("description", ""),
            required=value.get("required", True),
            default=value.get("default")
        )
        for key, value in config.input_schema.items()
    }
    
    # Convert output schema dict to ToolOutputSchema
    output_schema_data = config.output_schema
    output_schema = ToolOutputSchema(
        type=output_schema_data.get("type", "object"),
        description=output_schema_data.get("description", "")
    )
    
    # Create permission level
    try:
        permission_level = PermissionLevel(config.permission_level)
    except ValueError:
        logger.warning(f"Invalid permission level {config.permission_level}, using SAFE_ACTION")
        permission_level = PermissionLevel.SAFE_ACTION
    
    # Create and register the tool
    tool = Tool(
        name=config.name,
        description=config.description,
        input_schema=input_schema,
        output_schema=output_schema,
        permission_level=permission_level,
        domain=config.domain,
        category=config.category,
        execution_handler=execution_handler
    )
    
    tool_registry.register(tool)
    return tool


def register_skill_from_config(config: SkillConfig) -> Skill:
    """Create and register a Skill from configuration.
    
    Args:
        config: SkillConfig instance
    
    Returns:
        The registered Skill instance
    """
    # Create permission level
    try:
        permission_level = PermissionLevel(config.permission_level)
    except ValueError:
        logger.warning(f"Invalid permission level {config.permission_level}, using SAFE_ACTION")
        permission_level = PermissionLevel.SAFE_ACTION
    
    # Create and register the skill
    skill = Skill(
        name=config.name,
        description=config.description,
        domain=config.domain,
        required_tools=config.required_tools,
        capabilities=config.capabilities,
        instructions=config.instructions,
        execution_strategy=config.execution_strategy,
        permission_level=permission_level
    )
    
    skill_registry.register(skill)
    return skill


def load_and_apply_configurations() -> None:
    """Load configurations from file and apply them."""
    config_manager.load_from_file()
    config_manager.apply_configurations()


# Auto-load configurations on module import
try:
    load_and_apply_configurations()
except Exception as e:
    logger.warning(f"Could not load capability configurations: {e}")