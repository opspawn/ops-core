"""
Configuration loading module for ops-core.

Handles loading MCP server configurations from YAML files,
validating the structure, and resolving environment variables.
"""

import os
import yaml
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# Default path for the MCP server configuration file relative to the ops-core package root
DEFAULT_MCP_CONFIG_PATH = "config/mcp_servers.yaml"

class McpServerEnvVar(BaseModel):
    """Represents an environment variable mapping for an MCP server."""
    # Placeholder for potential future structure if needed, currently just uses Dict[str, str]
    pass

class McpServerConfig(BaseModel):
    """Pydantic model for validating individual MCP server configurations."""
    enabled: bool = True
    command: str
    script_path: Optional[str] = None
    args: Optional[List[str]] = None
    # Allow Any type initially, resolution function will convert to string
    env: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Removed field_validator for script_path/args as it wasn't strictly necessary
    # and could be overly complex depending on command types.

class McpConfig(BaseModel):
    """Pydantic model for validating the overall MCP configuration structure."""
    mcp_server_base_path: Optional[str] = None
    mcp_call_tool_timeout_seconds: float = Field(default=30.0, description="Default timeout in seconds for MCP call_tool requests.")
    database_url: str = Field(default="postgresql+asyncpg://user:password@localhost/opspawn_db", description="Database connection URL.")
    # Allow servers to be None initially, validator will default to {}
    servers: Optional[Dict[str, McpServerConfig]] = Field(default_factory=dict)

    @field_validator('servers', mode='before')
    @classmethod
    def empty_servers_to_dict(cls, v):
        """Convert None or empty input for 'servers' to an empty dict."""
        if v is None:
            return {}
        return v

def load_mcp_config(config_path: Optional[str] = None) -> McpConfig:
    """
    Loads MCP server configuration from a YAML file.

    Args:
        config_path: Optional path to the YAML configuration file.
                     If None, attempts to load from DEFAULT_MCP_CONFIG_PATH
                     relative to the ops_core package directory.

    Returns:
        An McpConfig object containing the validated configuration.

    Raises:
        FileNotFoundError: If the configuration file cannot be found.
        ValidationError: If the configuration file has an invalid structure.
        yaml.YAMLError: If the YAML file is malformed.
    """
    if config_path is None:
        # Determine path relative to this file's directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to ops_core/ and then join with default path
        package_root = os.path.dirname(current_dir)
        config_path = os.path.join(package_root, DEFAULT_MCP_CONFIG_PATH)

    print(f"Attempting to load MCP config from: {config_path}")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"MCP configuration file not found at {config_path}")

    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
            if not raw_config: # Handle empty file case
                raw_config = {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {config_path}: {e}")
        raise

    try:
        # Validate the structure using Pydantic
        validated_config = McpConfig(**raw_config)
        return validated_config
    except ValidationError as e:
        print(f"MCP configuration validation error in {config_path}: {e}")
        raise

def resolve_environment_variables(config: McpConfig) -> McpConfig:
    """
    Resolves environment variable placeholders (e.g., ${VAR_NAME})
    within the loaded MCP configuration.

    Args:
        config: The loaded McpConfig object.

    Returns:
        A new McpConfig object with environment variables resolved.
        Unresolvable variables will result in an error or be left as is,
        depending on desired behavior (currently raises ValueError).

    Raises:
        ValueError: If an environment variable placeholder cannot be resolved.
    """
    resolved_servers: Dict[str, McpServerConfig] = {}
    for name, server_conf in config.servers.items():
        resolved_env: Dict[str, str] = {}
        if server_conf.env:
            for key, value_placeholder in server_conf.env.items():
                if isinstance(value_placeholder, str) and value_placeholder.startswith('${') and value_placeholder.endswith('}'):
                    var_name = value_placeholder[2:-1]
                    resolved_value = os.environ.get(var_name)
                    if resolved_value is None:
                        # Raise error if variable not found (current behavior)
                        raise ValueError(f"Environment variable '{var_name}' needed by MCP server '{name}' is not set.")
                    resolved_env[key] = resolved_value
                else:
                    # Ensure non-placeholder values are strings after resolution
                    resolved_env[key] = str(value_placeholder)

        # Create a new McpServerConfig with resolved env
        server_data = server_conf.model_dump(exclude={'env'}) # Get data excluding env
        server_data['env'] = resolved_env # Add resolved env
        resolved_servers[name] = McpServerConfig(**server_data)


    # Create a new McpConfig with resolved servers
    resolved_config_data = config.model_dump(exclude={'servers'})
    resolved_config_data['servers'] = resolved_servers
    return McpConfig(**resolved_config_data)


def get_resolved_mcp_config(config_path: Optional[str] = None) -> McpConfig:
    """
    Loads, validates, and resolves environment variables for the MCP config.

    Args:
        config_path: Optional path to the YAML configuration file.

    Returns:
        The fully processed and validated McpConfig object.
    """
    loaded_config = load_mcp_config(config_path)
    resolved_config = resolve_environment_variables(loaded_config)

    # Resolve DATABASE_URL from environment variable, keeping default if not set
    db_url_from_env = os.environ.get("DATABASE_URL")
    if db_url_from_env:
        resolved_config.database_url = db_url_from_env
    # Otherwise, the default value set in the model field definition is used

    return resolved_config

# Example usage (for testing purposes)
if __name__ == "__main__":
    try:
        # Create a dummy config file for testing relative path loading
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dummy_config_dir = os.path.join(os.path.dirname(current_dir)) # ops_core/
        dummy_config_path = os.path.join(dummy_config_dir, DEFAULT_MCP_CONFIG_PATH)

        # Ensure the dummy config directory exists
        os.makedirs(os.path.dirname(dummy_config_path), exist_ok=True)

        # Set dummy env var for testing resolution
        os.environ['TEST_API_KEY'] = 'dummy-key-123'

        dummy_yaml_content = """
mcp_server_base_path: /tmp/mcp_servers
servers:
  test-server:
    enabled: true
    command: python
    script_path: test_server.py
    env:
      API_KEY: ${TEST_API_KEY}
      FIXED_VAR: "some_value"
  disabled-server:
    enabled: false
    command: node
    args: ["server.js"]
"""
        with open(dummy_config_path, 'w') as f:
            f.write(dummy_yaml_content)

        print(f"Created dummy config at: {dummy_config_path}")

        # Test loading the default config
        resolved_config = get_resolved_mcp_config() # Uses default path mechanism
        print("\nResolved Configuration:")
        print(resolved_config.model_dump_json(indent=2))

        # Test with DATABASE_URL override
        print("\nTesting with DATABASE_URL override...")
        os.environ['DATABASE_URL'] = 'postgresql+asyncpg://test_user:test_pass@testhost/testdb'
        resolved_config_override = get_resolved_mcp_config()
        print(resolved_config_override.model_dump_json(indent=2))
        del os.environ['DATABASE_URL']


        # Clean up dummy file and env var
        os.remove(dummy_config_path)
        del os.environ['TEST_API_KEY']
        print(f"\nCleaned up dummy config and env var.")

    except (FileNotFoundError, ValidationError, ValueError, yaml.YAMLError) as e:
        print(f"\nError during example execution: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
