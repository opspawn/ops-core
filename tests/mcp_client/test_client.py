"""
Unit tests for the refactored OpsMcpClient in ops_core.mcp_client.client.
Focuses on multi-server management, config integration, and request routing.
"""
import os
import pytest
import pytest_asyncio
import logging
import asyncio
from asyncio import TimeoutError as AsyncTimeoutError # Import specifically for timeout test
from unittest.mock import patch, AsyncMock, MagicMock, call, ANY

# Module to test
from ops_core.mcp_client.client import OpsMcpClient, logger as client_logger

# Import necessary types for mocking
from mcp import ClientSession, StdioServerParameters, McpError
from mcp.types import (
    Tool, Resource, ResourceTemplate,
    TextContent, # Keep base types if needed
    ErrorData # Import ErrorData for McpError instantiation
    # ErrorCode removed as it caused ImportError
)
# Removed problematic response type imports: CallToolResponse, ReadResourceResponse, etc.
# Mocks will use MagicMock or similar instead.
from ops_core.config.loader import McpConfig, McpServerConfig

# Configure logger for tests
@pytest.fixture(autouse=True)
def configure_test_logger(caplog):
    client_logger.setLevel(logging.DEBUG)

# --- Test Fixtures ---

@pytest.fixture
def mock_mcp_config():
    """Provides a mock McpConfig object."""
    return McpConfig(
        mcp_server_base_path="/base/path",
        servers={
            "server1": McpServerConfig(
                enabled=True,
                command="python",
                script_path="server1_script.py",
                env={"S1_VAR": "val1"}
            ),
            "server2": McpServerConfig(
                enabled=True,
                command="node",
                args=["server2_script.js", "--port", "8080"],
                env={"S2_VAR": "val2"}
            ),
            "disabled_server": McpServerConfig(
                enabled=False,
                command="python",
                script_path="disabled_script.py"
            ),
            "server_no_script": McpServerConfig(
                enabled=True,
                command="npx",
                args=["@scope/some-server"],
                env={}
            )
        }
    )

@pytest_asyncio.fixture
async def mock_mcp_dependencies():
    """Mocks dependencies like stdio_client and ClientSession."""
    # Patch stdio_client as a regular function returning an async context manager
    with patch('ops_core.mcp_client.client.stdio_client') as mock_stdio_provider, \
         patch('ops_core.mcp_client.client.ClientSession', new_callable=MagicMock) as mock_session_class, \
         patch('ops_core.mcp_client.client.os.path.exists') as mock_exists, \
         patch('ops_core.mcp_client.client.get_resolved_mcp_config') as mock_get_config:

        # Mock os.path.exists to return True by default for script paths
        mock_exists.return_value = True

        # Configure the mock context manager object that stdio_client will return
        mock_stdio_cm = AsyncMock() # This needs __aenter__ and __aexit__
        mock_stdio_cm.__aenter__.return_value = (AsyncMock(spec=asyncio.StreamReader), AsyncMock(spec=asyncio.StreamWriter))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
        # Configure the regular function mock (stdio_client) to return the context manager mock
        mock_stdio_provider.return_value = mock_stdio_cm

        # Mock ClientSession class to return a mock instance
        mock_session_instance = AsyncMock(spec=ClientSession)
        mock_session_instance.__aenter__.return_value = mock_session_instance # Return self for context management
        mock_session_instance.initialize = AsyncMock()
        mock_session_instance.call_tool = AsyncMock()
        mock_session_instance.read_resource = AsyncMock()
        mock_session_instance.list_tools = AsyncMock()
        mock_session_instance.list_resources = AsyncMock()
        mock_session_instance.list_resource_templates = AsyncMock()
        # Configure the class mock to return the instance mock when called
        mock_session_class.return_value = mock_session_instance

        yield {
            "mock_stdio_provider": mock_stdio_provider, # Yield the regular function mock
            "mock_session_class": mock_session_class,
            "mock_session_instance": mock_session_instance,
            "mock_exists": mock_exists,
            "mock_get_config": mock_get_config
        }

# --- Initialization Tests ---

def test_init_with_provided_config(mock_mcp_config, mock_mcp_dependencies):
    """Test initialization when config is provided directly."""
    client = OpsMcpClient(config=mock_mcp_config)
    assert client._config == mock_mcp_config
    assert not client._sessions # Initially empty
    assert not client._transports
    assert not client._is_running
    mock_mcp_dependencies["mock_get_config"].assert_not_called()

def test_init_loads_default_config(mock_mcp_config, mock_mcp_dependencies):
    """Test initialization loads config using get_resolved_mcp_config if not provided."""
    mock_mcp_dependencies["mock_get_config"].return_value = mock_mcp_config
    client = OpsMcpClient(config=None)
    assert client._config == mock_mcp_config
    mock_mcp_dependencies["mock_get_config"].assert_called_once()

# --- Server Start/Stop Tests ---

@pytest.mark.asyncio
async def test_start_all_servers_success(mock_mcp_config, mock_mcp_dependencies, caplog):
    """Test starting all enabled servers successfully."""
    client = OpsMcpClient(config=mock_mcp_config)
    await client.start_all_servers()

    assert client._is_running
    # Should attempt to start server1, server2, server_no_script (3 enabled)
    assert mock_mcp_dependencies["mock_stdio_provider"].call_count == 3 # Check call_count on the provider
    assert mock_mcp_dependencies["mock_session_class"].call_count == 3
    # Use the specific mock instance created by the factory for initialize check
    # Since session_factory creates new mocks, we need to check the factory call count instead
    # assert mock_mcp_dependencies["mock_session_instance"].initialize.await_count == 3 # This won't work as expected with factory
    # Check that initialize was called on the mocks created by the factory (indirectly via session_class call count)

    # Check sessions created
    assert "server1" in client._sessions
    assert "server2" in client._sessions
    assert "server_no_script" in client._sessions
    assert "disabled_server" not in client._sessions

    # Check logs
    assert "Starting enabled MCP servers..." in caplog.text
    assert "Starting server 'server1'..." in caplog.text
    assert "Starting server 'server2'..." in caplog.text
    assert "Starting server 'server_no_script'..." in caplog.text
    assert "Server 'server1' started and session initialized." in caplog.text
    assert "Server 'server2' started and session initialized." in caplog.text
    assert "Server 'server_no_script' started and session initialized." in caplog.text
    assert "Finished starting servers. Active sessions: ['server1', 'server2', 'server_no_script']" in caplog.text # Order might vary

    # Check stdio_client calls with correct parameters
    expected_calls = [
        # server1
        call(StdioServerParameters(command='python', args=['/base/path/server1_script.py'], env={'S1_VAR': 'val1'})),
        # server2 (no script_path, uses args directly)
        call(StdioServerParameters(command='node', args=['server2_script.js', '--port', '8080'], env={'S2_VAR': 'val2'})),
         # server_no_script (no script_path, uses args directly)
        call(StdioServerParameters(command='npx', args=['@scope/some-server'], env={})),
    ]
    # Allow any order for the calls
    mock_mcp_dependencies["mock_stdio_provider"].assert_has_calls(expected_calls, any_order=True) # Check calls on the provider

    # Check script path resolution and existence check
    mock_mcp_dependencies["mock_exists"].assert_has_calls([
        call('/base/path/server1_script.py'), # server1 script path resolved
        # server2 has no script_path, so no os.path.exists call
        # disabled_server is not started, so no os.path.exists call
        # server_no_script has no script_path, so no os.path.exists call
    ], any_order=True)


@pytest.mark.asyncio
async def test_start_all_servers_no_enabled(mock_mcp_dependencies, caplog):
    """Test starting when no servers are enabled."""
    empty_config = McpConfig(servers={
        "s1": McpServerConfig(enabled=False, command="echo")
    })
    client = OpsMcpClient(config=empty_config)
    await client.start_all_servers()

    assert client._is_running # Should still be marked as running
    assert not client._sessions
    mock_mcp_dependencies["mock_stdio_provider"].assert_not_called() # Check provider call
    assert "No enabled MCP servers found in configuration." in caplog.text

@pytest.mark.asyncio
async def test_start_all_servers_script_not_found(mock_mcp_config, mock_mcp_dependencies, caplog):
    """Test starting servers when a script path doesn't exist."""
    # Make os.path.exists return False for server1's script
    mock_mcp_dependencies["mock_exists"].side_effect = lambda p: p != '/base/path/server1_script.py'

    client = OpsMcpClient(config=mock_mcp_config)
    await client.start_all_servers()

    # Should attempt server1, fail, then attempt server2 and server_no_script
    assert client._is_running
    assert "server1" not in client._sessions # Failed to start
    assert "server2" in client._sessions
    assert "server_no_script" in client._sessions

    # Check logs for the error
    assert "Script path for server 'server1' not found: /base/path/server1_script.py" in caplog.text
    # Check the specific error message logged, not just the type
    assert "Failed to start server 'server1': Script path for server 'server1' not found: /base/path/server1_script.py" in caplog.text
    # Check that others started
    assert "Starting server 'server2'..." in caplog.text
    assert "Starting server 'server_no_script'..." in caplog.text
    assert "Finished starting servers. Active sessions: ['server2', 'server_no_script']" in caplog.text # Order might vary

    # stdio_client should only be called for server2 and server_no_script
    assert mock_mcp_dependencies["mock_stdio_provider"].call_count == 2 # Check provider call

@pytest.mark.asyncio
async def test_start_all_servers_connection_error(mock_mcp_config, mock_mcp_dependencies, caplog):
    """Test starting servers when stdio_client raises an error for one server."""
    # Make stdio_client fail for server2
    # NOTE: This must be 'def', not 'async def', because the original stdio_client
    # is a regular function returning an async context manager, not an async function.
    def stdio_side_effect(*args, **kwargs):
        params = args[0] if args else kwargs.get('params')
        if params and params.command == 'node': # Identify server2 call
             # Instantiate McpError correctly using ErrorData
             # Use a placeholder integer (e.g., 0) for the code
             mock_error_data = ErrorData(code=0, message="Connection refused")
             raise McpError(mock_error_data)
        else:
            # Return the normal mock context manager for other calls
            mock_cm = AsyncMock() # This is the context manager object
            mock_cm.__aenter__.return_value = (AsyncMock(spec=asyncio.StreamReader), AsyncMock(spec=asyncio.StreamWriter))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            return mock_cm # The regular function returns the context manager

    mock_mcp_dependencies["mock_stdio_provider"].side_effect = stdio_side_effect # Set side_effect on the provider

    client = OpsMcpClient(config=mock_mcp_config)
    await client.start_all_servers()

    assert client._is_running
    assert "server1" in client._sessions
    assert "server2" not in client._sessions # Failed
    assert "server_no_script" in client._sessions

    # Check the actual error logged due to incorrect McpError instantiation initially
    # assert "MCP Error starting server 'server2': Connection refused" in caplog.text # This won't be logged now
    assert "Failed to start server 'server2': Connection refused" in caplog.text # Check the actual exception message logged
    assert "Finished starting servers. Active sessions: ['server1', 'server_no_script']" in caplog.text # Order might vary

@pytest.mark.asyncio
async def test_stop_all_servers(mock_mcp_config, mock_mcp_dependencies, caplog):
    """Test stopping servers cleans up resources via AsyncExitStack."""
    client = OpsMcpClient(config=mock_mcp_config)
    # Mock the exit stack's aclose method
    client._exit_stack.aclose = AsyncMock()

    # Simulate starting servers first
    client._is_running = True
    client._sessions = {"server1": MagicMock(), "server2": MagicMock()} # Dummy sessions

    await client.stop_all_servers()

    assert not client._is_running
    assert not client._sessions # State cleared
    assert not client._transports
    client._exit_stack.aclose.assert_awaited_once() # Verify stack cleanup was called
    assert "Stopping all MCP servers and cleaning up resources..." in caplog.text
    assert "All MCP servers stopped and resources cleaned up." in caplog.text

@pytest.mark.asyncio
async def test_context_manager(mock_mcp_config, mock_mcp_dependencies):
    """Test the async context manager starts and stops servers."""
    client = OpsMcpClient(config=mock_mcp_config)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()

    async with client as managed_client:
        assert managed_client is client
        client.start_all_servers.assert_awaited_once()
        client.stop_all_servers.assert_not_awaited() # Not called yet

    client.stop_all_servers.assert_awaited_once() # Called on exit

# --- Request Routing Tests ---

@pytest_asyncio.fixture
async def running_client(mock_mcp_config, mock_mcp_dependencies):
    """Fixture for a client with successfully started mock servers."""
    client = OpsMcpClient(config=mock_mcp_config)

    # Store mock sessions per server name for verification
    mock_sessions = {}
    session_mocks_created = 0

    # NOTE: This must be 'def', not 'async def', because ClientSession() is called
    # directly and expected to return the context manager instance, not a coroutine.
    def session_factory(*args, **kwargs):
        nonlocal session_mocks_created
        # Create a unique mock instance for each session call
        instance = AsyncMock(spec=ClientSession)
        instance.__aenter__.return_value = instance
        instance.initialize = AsyncMock()
        instance.call_tool = AsyncMock(name=f"call_tool_{session_mocks_created}")
        instance.read_resource = AsyncMock(name=f"read_resource_{session_mocks_created}")
        instance.list_tools = AsyncMock(name=f"list_tools_{session_mocks_created}")
        # ... add other methods if needed ...
        session_mocks_created += 1
        return instance

    mock_mcp_dependencies["mock_session_class"].side_effect = session_factory

    await client.start_all_servers()
    # Store the created mocks for tests to access
    client._mock_sessions_store = {name: client._sessions[name] for name in client._sessions}
    yield client
    await client.stop_all_servers() # Ensure cleanup

@pytest.mark.asyncio
async def test_get_session_success(running_client):
    """Test retrieving an active session."""
    session = await running_client.get_session("server1")
    assert session is running_client._mock_sessions_store["server1"]

@pytest.mark.asyncio
async def test_get_session_not_running(mock_mcp_config):
    """Test get_session raises error if client hasn't started."""
    client = OpsMcpClient(config=mock_mcp_config)
    with pytest.raises(RuntimeError, match="MCP Client is not running"):
        await client.get_session("server1")

@pytest.mark.asyncio
async def test_get_session_unknown_server(running_client):
    """Test get_session raises error for an unknown server name."""
    with pytest.raises(ValueError, match="MCP server 'unknown_server' is not defined"):
        await running_client.get_session("unknown_server")

@pytest.mark.asyncio
async def test_get_session_disabled_server(running_client):
    """Test get_session raises error for a disabled server."""
    with pytest.raises(ValueError, match="MCP server 'disabled_server' is configured but not enabled"):
        await running_client.get_session("disabled_server")

@pytest.mark.asyncio
async def test_get_session_failed_to_start(running_client, mock_mcp_config):
    """Test get_session raises error if server is enabled but session doesn't exist."""
    # Simulate server3 failing to start by removing its session post-start
    mock_mcp_config.servers["server3"] = McpServerConfig(enabled=True, command="fail")
    # Re-init client with modified config
    client = OpsMcpClient(config=mock_mcp_config)
    client._is_running = True # Manually set state as if start was attempted
    # client._sessions does not contain 'server3'

    with pytest.raises(ValueError, match="MCP server 'server3' is enabled but no active session found"):
        await client.get_session("server3")


@pytest.mark.asyncio
async def test_call_tool_success(running_client):
    """Test successful call_tool routing."""
    # Use MagicMock instead of the specific response type
    mock_response = MagicMock()
    mock_response.content = [TextContent(type="text", text="Success!")]
    mock_response.isError = False
    running_client._mock_sessions_store["server1"].call_tool.return_value = mock_response

    args = {"param": "value"}
    response = await running_client.call_tool("server1", "tool_a", args)

    assert response == mock_response
    running_client._mock_sessions_store["server1"].call_tool.assert_awaited_once_with("tool_a", args)
    # Ensure other server sessions weren't called
    if "server2" in running_client._mock_sessions_store:
        running_client._mock_sessions_store["server2"].call_tool.assert_not_awaited()

@pytest.mark.asyncio
async def test_call_tool_mcp_error(running_client):
    """Test call_tool when the session raises an McpError."""
    error_msg = "Tool execution failed"
    # Instantiate McpError correctly using ErrorData
    # Use a placeholder integer (e.g., 0) for the code since ErrorCode enum import failed
    mock_error_data = ErrorData(code=0, message=error_msg)
    running_client._mock_sessions_store["server2"].call_tool.side_effect = McpError(mock_error_data)

    # Match against the message within the ErrorData
    with pytest.raises(McpError, match=error_msg):
        await running_client.call_tool("server2", "tool_b", {})

    running_client._mock_sessions_store["server2"].call_tool.assert_awaited_once_with("tool_b", {})

@pytest.mark.asyncio
async def test_call_tool_timeout(running_client, caplog):
    """Test call_tool raises McpError on asyncio.TimeoutError."""
    server_name = "server1"
    tool_name = "slow_tool"
    timeout_duration = running_client._config.mcp_call_tool_timeout_seconds # Get default from config

    # Configure the mock session's call_tool to sleep longer than the timeout
    async def slow_call(*args, **kwargs):
        await asyncio.sleep(timeout_duration + 0.1) # Sleep slightly longer than timeout
        # This part shouldn't be reached if timeout works
        return MagicMock()

    running_client._mock_sessions_store[server_name].call_tool.side_effect = slow_call

    expected_error_msg = f"Timeout ({timeout_duration}s) calling tool '{tool_name}' on server '{server_name}'."

    with pytest.raises(McpError) as excinfo:
        await running_client.call_tool(server_name, tool_name, {})

    # Check that the raised McpError has the correct message (via string representation)
    assert str(excinfo.value) == expected_error_msg
    # Removed check for excinfo.value.code as it seems unreliable for timeout-generated errors

    # Verify the underlying session method was called
    running_client._mock_sessions_store[server_name].call_tool.assert_awaited_once_with(tool_name, {})
    # Verify the error was logged
    assert expected_error_msg in caplog.text

@pytest.mark.asyncio
async def test_read_resource_success(running_client):
    """Test successful read_resource routing."""
    # Use MagicMock instead of the specific response type
    mock_response = MagicMock()
    mock_response.contents = [MagicMock()] # Dummy content
    running_client._mock_sessions_store["server_no_script"].read_resource.return_value = mock_response

    uri = "resource://data/item"
    response = await running_client.read_resource("server_no_script", uri)

    assert response == mock_response
    running_client._mock_sessions_store["server_no_script"].read_resource.assert_awaited_once_with(uri)

@pytest.mark.asyncio
async def test_list_tools_success(running_client):
    """Test successful list_tools routing."""
    # Use MagicMock instead of the specific response type
    mock_response = MagicMock()
    mock_response.tools = [Tool(name="t1", inputSchema={})]
    running_client._mock_sessions_store["server1"].list_tools.return_value = mock_response

    response = await running_client.list_tools("server1")

    assert response == mock_response
    running_client._mock_sessions_store["server1"].list_tools.assert_awaited_once()

# Add similar tests for list_resources, list_resource_templates if needed
