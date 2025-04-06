"""
Unit tests for the configuration loader in ops_core.config.loader.
"""

import os
import pytest
import yaml
from pydantic import ValidationError
from unittest.mock import patch, mock_open

# Module to test
from ops_core.config.loader import (
    load_mcp_config,
    resolve_environment_variables,
    get_resolved_mcp_config,
    McpConfig,
    McpServerConfig,
    DEFAULT_MCP_CONFIG_PATH
)

# Helper function to create dummy config content
def create_dummy_yaml_content(
    base_path: str = "/tmp/mcp",
    api_key_placeholder: str = "${TEST_API_KEY}",
    fixed_var: str = "fixed_value"
) -> str:
    return f"""
mcp_server_base_path: {base_path}
servers:
  test-server-py:
    enabled: true
    command: python
    script_path: server1.py
    env:
      API_KEY: {api_key_placeholder}
      FIXED_VAR: "{fixed_var}"
  test-server-npx:
    enabled: true
    command: npx
    args: ["@scope/server2"]
    env:
      ANOTHER_KEY: ${{ANOTHER_KEY}}
  disabled-server:
    enabled: false
    command: python
    script_path: server3.py
"""

@pytest.fixture
def mock_env_vars():
    """Fixture to temporarily set environment variables."""
    original_env = os.environ.copy()
    os.environ['TEST_API_KEY'] = 'key123'
    os.environ['ANOTHER_KEY'] = 'key456'
    yield
    os.environ.clear()
    os.environ.update(original_env)

# --- Tests for load_mcp_config ---

def test_load_mcp_config_success():
    """Test loading a valid configuration file."""
    yaml_content = create_dummy_yaml_content()
    mock_file = mock_open(read_data=yaml_content)
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        config = load_mcp_config("dummy_path.yaml")

    assert isinstance(config, McpConfig)
    assert config.mcp_server_base_path == "/tmp/mcp"
    assert "test-server-py" in config.servers
    assert config.servers["test-server-py"].command == "python"
    assert config.servers["test-server-py"].script_path == "server1.py"
    assert config.servers["test-server-py"].env == {"API_KEY": "${TEST_API_KEY}", "FIXED_VAR": "fixed_value"}
    assert "disabled-server" in config.servers
    assert not config.servers["disabled-server"].enabled

def test_load_mcp_config_file_not_found():
    """Test loading when the config file does not exist."""
    with patch('os.path.exists', return_value=False):
        with pytest.raises(FileNotFoundError):
            load_mcp_config("non_existent_path.yaml")

def test_load_mcp_config_malformed_yaml():
    """Test loading a file with invalid YAML syntax."""
    malformed_yaml = "servers: \n  test:\n command: python\n    script_path: server.py" # Bad indentation
    mock_file = mock_open(read_data=malformed_yaml)
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        with pytest.raises(yaml.YAMLError):
            load_mcp_config("malformed.yaml")

def test_load_mcp_config_validation_error():
    """Test loading a file with valid YAML but invalid structure."""
    invalid_structure_yaml = """
servers:
  test-server:
    # Missing 'command' field
    script_path: server.py
"""
    mock_file = mock_open(read_data=invalid_structure_yaml)
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        with pytest.raises(ValidationError):
            load_mcp_config("invalid_structure.yaml")

def test_load_mcp_config_empty_file():
    """Test loading an empty YAML file."""
    mock_file = mock_open(read_data="")
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        config = load_mcp_config("empty.yaml")
    assert isinstance(config, McpConfig)
    assert config.mcp_server_base_path is None
    assert config.servers == {}

def test_load_mcp_config_empty_servers_dict():
    """Test loading YAML with an empty 'servers' dictionary."""
    yaml_content = "servers: {}"
    mock_file = mock_open(read_data=yaml_content)
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        config = load_mcp_config("empty_servers.yaml")
    assert isinstance(config, McpConfig)
    assert config.servers == {}

def test_load_mcp_config_null_servers_dict():
    """Test loading YAML where 'servers' is null."""
    yaml_content = "servers: null" # Or servers:
    mock_file = mock_open(read_data=yaml_content)
    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        config = load_mcp_config("null_servers.yaml")
    assert isinstance(config, McpConfig)
    # Pydantic should initialize servers to its default factory (empty dict)
    assert config.servers == {}


# --- Tests for Pydantic Models ---

def test_mcp_server_config_defaults():
    """Test default values for McpServerConfig."""
    # Minimal valid config
    config = McpServerConfig(command="echo", args=["hello"])
    assert config.enabled is True
    assert config.script_path is None
    assert config.env == {} # Defaults to empty dict

    # Explicitly disabling
    config_disabled = McpServerConfig(command="echo", enabled=False)
    assert config_disabled.enabled is False

    # With script path
    config_script = McpServerConfig(command="python", script_path="run.py")
    assert config_script.script_path == "run.py"
    assert config_script.args is None


# --- Tests for resolve_environment_variables ---

def test_resolve_environment_variables_success(mock_env_vars):
    """Test resolving environment variables successfully."""
    raw_config_dict = yaml.safe_load(create_dummy_yaml_content())
    config = McpConfig(**raw_config_dict)

    resolved_config = resolve_environment_variables(config)

    assert resolved_config.servers["test-server-py"].env["API_KEY"] == "key123"
    assert resolved_config.servers["test-server-py"].env["FIXED_VAR"] == "fixed_value" # Unchanged
    assert resolved_config.servers["test-server-npx"].env["ANOTHER_KEY"] == "key456"
    # Ensure disabled server env is also processed (though it might not be used)
    assert resolved_config.servers["disabled-server"].env == {} # Original was None, defaults to {}

def test_resolve_environment_variables_missing_var(mock_env_vars):
    """Test resolving when a required environment variable is missing."""
    # Remove one of the expected keys
    del os.environ['ANOTHER_KEY']

    raw_config_dict = yaml.safe_load(create_dummy_yaml_content())
    config = McpConfig(**raw_config_dict)

    with pytest.raises(ValueError, match="Environment variable 'ANOTHER_KEY' needed by MCP server 'test-server-npx' is not set."):
        resolve_environment_variables(config)

def test_resolve_environment_variables_no_env_section():
    """Test resolving when a server config has no 'env' section."""
    yaml_content = """
servers:
  no-env-server:
    command: bash
    script_path: run.sh
"""
    raw_config_dict = yaml.safe_load(yaml_content)
    config = McpConfig(**raw_config_dict)
    resolved_config = resolve_environment_variables(config)
    assert resolved_config.servers["no-env-server"].env == {} # Should default to empty dict

def test_resolve_environment_variables_empty_env_dict():
    """Test resolving when a server's env dict is present but empty."""
    yaml_content = """
servers:
  empty-env-server:
    command: echo
    args: ["test"]
    env: {}
"""
    raw_config_dict = yaml.safe_load(yaml_content)
    config = McpConfig(**raw_config_dict)
    resolved_config = resolve_environment_variables(config)
    assert resolved_config.servers["empty-env-server"].env == {}

def test_resolve_environment_variables_non_placeholder_value(mock_env_vars):
    """Test resolving when an env value is not a placeholder string."""
    yaml_content = """
servers:
  mixed-env-server:
    command: echo
    env:
      KEY1: ${TEST_API_KEY}
      KEY2: 12345
      KEY3: true
      KEY4: "literal_string"
"""
    raw_config_dict = yaml.safe_load(yaml_content)
    config = McpConfig(**raw_config_dict)
    resolved_config = resolve_environment_variables(config)
    assert resolved_config.servers["mixed-env-server"].env["KEY1"] == "key123"
    assert resolved_config.servers["mixed-env-server"].env["KEY2"] == "12345" # Converted to string
    assert resolved_config.servers["mixed-env-server"].env["KEY3"] == "True"  # Converted to string
    assert resolved_config.servers["mixed-env-server"].env["KEY4"] == "literal_string"

def test_resolve_environment_variables_empty_servers():
    """Test resolving when the main servers dict is empty."""
    config = McpConfig(servers={})
    resolved_config = resolve_environment_variables(config)
    assert resolved_config.servers == {}

def test_resolve_environment_variables_base_path(mock_env_vars):
    """Test resolving environment variables in mcp_server_base_path."""
    os.environ['BASE_DIR'] = '/resolved/base/path'
    yaml_content = """
mcp_server_base_path: ${BASE_DIR}/servers
servers:
  test-server:
    command: echo
    env:
      API_KEY: ${TEST_API_KEY}
"""
    raw_config_dict = yaml.safe_load(yaml_content)
    config = McpConfig(**raw_config_dict)
    # NOTE: Current implementation of resolve_environment_variables *only* resolves within server envs.
    # This test confirms that mcp_server_base_path is NOT resolved by this specific function.
    # If base path resolution is needed, it would require modifying resolve_environment_variables.
    resolved_config = resolve_environment_variables(config)
    assert resolved_config.mcp_server_base_path == "${BASE_DIR}/servers" # Unchanged by this function
    assert resolved_config.servers["test-server"].env["API_KEY"] == "key123"
    del os.environ['BASE_DIR'] # Clean up test env var

def test_resolve_environment_variables_complex_values(mock_env_vars):
    """Test resolving env vars with values that look like numbers/booleans."""
    os.environ['NUM_STR'] = '12345'
    os.environ['BOOL_STR'] = 'False'
    os.environ['SPECIAL_CHARS'] = 'key=value;another=pair!'

    yaml_content = """
servers:
  complex-env-server:
    command: echo
    env:
      NUM_KEY: ${NUM_STR}
      BOOL_KEY: ${BOOL_STR}
      SPECIAL_KEY: ${SPECIAL_CHARS}
      REGULAR_KEY: ${TEST_API_KEY}
"""
    raw_config_dict = yaml.safe_load(yaml_content)
    config = McpConfig(**raw_config_dict)
    resolved_config = resolve_environment_variables(config)

    assert resolved_config.servers["complex-env-server"].env["NUM_KEY"] == "12345"
    assert isinstance(resolved_config.servers["complex-env-server"].env["NUM_KEY"], str)
    assert resolved_config.servers["complex-env-server"].env["BOOL_KEY"] == "False"
    assert isinstance(resolved_config.servers["complex-env-server"].env["BOOL_KEY"], str)
    assert resolved_config.servers["complex-env-server"].env["SPECIAL_KEY"] == "key=value;another=pair!"
    assert resolved_config.servers["complex-env-server"].env["REGULAR_KEY"] == "key123"

    # Clean up test env vars
    del os.environ['NUM_STR']
    del os.environ['BOOL_STR']
    del os.environ['SPECIAL_CHARS']


# --- Tests for get_resolved_mcp_config ---

@patch('ops_core.config.loader.load_mcp_config')
@patch('ops_core.config.loader.resolve_environment_variables')
def test_get_resolved_mcp_config_mocked(mock_resolve, mock_load):
    """Test the main function orchestrates loading and resolving."""
    mock_loaded_config = McpConfig(servers={"test": McpServerConfig(command="echo")})
    mock_resolved_config = McpConfig(servers={"test": McpServerConfig(command="echo", env={"RESOLVED": "yes"})})

    mock_load.return_value = mock_loaded_config
    mock_resolve.return_value = mock_resolved_config

    result = get_resolved_mcp_config("some_path.yaml")

    mock_load.assert_called_once_with("some_path.yaml")
    mock_resolve.assert_called_once_with(mock_loaded_config)
    assert result == mock_resolved_config

def test_get_resolved_mcp_config_integration(mock_env_vars):
    """Integration test for get_resolved_mcp_config using mocks for IO."""
    yaml_content = create_dummy_yaml_content()
    mock_file = mock_open(read_data=yaml_content)

    with patch('builtins.open', mock_file), \
         patch('os.path.exists', return_value=True):
        resolved_config = get_resolved_mcp_config("dummy_path.yaml")

    # Verify results after loading and resolving
    assert isinstance(resolved_config, McpConfig)
    assert resolved_config.mcp_server_base_path == "/tmp/mcp"
    assert "test-server-py" in resolved_config.servers
    assert resolved_config.servers["test-server-py"].env["API_KEY"] == "key123"
    assert resolved_config.servers["test-server-py"].env["FIXED_VAR"] == "fixed_value"
    assert "test-server-npx" in resolved_config.servers
    assert resolved_config.servers["test-server-npx"].env["ANOTHER_KEY"] == "key456"
    assert "disabled-server" in resolved_config.servers
    assert not resolved_config.servers["disabled-server"].enabled
    assert resolved_config.servers["disabled-server"].env == {}


# --- Test Default Path Loading ---
# This requires mocking the path calculation relative to the loader module

@patch('os.path.exists')
@patch('builtins.open')
def test_load_mcp_config_default_path(mock_open_builtin, mock_exists):
    """Test loading using the default config path mechanism."""
    # Calculate the expected default path exactly as done in loader.py
    # Get the directory containing loader.py
    loader_module_dir = os.path.dirname(os.path.abspath(load_mcp_config.__code__.co_filename))
    # Get the package root (one level up from loader.py's directory)
    package_root_dir = os.path.dirname(loader_module_dir)
    # Join with the default config path filename
    expected_default_path = os.path.join(package_root_dir, DEFAULT_MCP_CONFIG_PATH)

    mock_exists.return_value = True
    # Configure mock_open to return a context manager compatible mock
    mock_file_context = mock_open(read_data=create_dummy_yaml_content()).return_value
    mock_file_context.__enter__.return_value = mock_file_context
    mock_file_context.__exit__.return_value = None
    mock_open_builtin.return_value = mock_file_context

    # Call load_mcp_config with config_path=None to trigger default path logic
    config = load_mcp_config(config_path=None)

    # Assert that os.path.exists and open were called with the calculated default path
    mock_exists.assert_called_with(expected_default_path)
    mock_open_builtin.assert_called_with(expected_default_path, 'r')
    assert isinstance(config, McpConfig) # Check if loading was successful
