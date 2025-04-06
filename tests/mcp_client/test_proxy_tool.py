import pytest
from unittest.mock import MagicMock, AsyncMock

from pydantic import ValidationError

from ops_core.mcp_client.proxy_tool import MCPProxyTool
# Import ToolError as well
from agentkit.tools.schemas import ToolResult, ToolSpec, ToolError # Assuming agentkit is installed
from agentkit.tools.mcp_proxy import MCPProxyToolInput  # Assuming agentkit is installed

# Import the actual client class for spec
from ops_core.mcp_client.client import OpsMcpClient


@pytest.fixture
def mock_mcp_client():
    """Fixture for a mocked OpsMcpClient."""
    # Use spec=OpsMcpClient to make the mock pass isinstance checks
    client = MagicMock(spec=OpsMcpClient)
    client.call_tool = AsyncMock()
    return client


# Fixture now correctly initializes the tool
@pytest.fixture
def mcp_proxy_tool(mock_mcp_client):
    """Fixture for MCPProxyTool initialized with a mock client."""
    # Pass the client as a positional argument
    return MCPProxyTool(mock_mcp_client)


@pytest.mark.asyncio
async def test_mcp_proxy_tool_execute_success(mcp_proxy_tool, mock_mcp_client): # Use fixture, test execute
    """Test MCPProxyTool.execute successfully calls client.call_tool."""
    # Tool input model
    tool_input_model = MCPProxyToolInput(
        server_name="test-server",
        tool_name="test_tool",
        arguments={"arg1": "value1", "arg2": 123},
    )
    # Convert model to dict for execute method
    tool_input_dict = tool_input_model.model_dump()

    expected_mcp_result = {"status": "success", "data": "mocked result"}
    mock_mcp_client.call_tool.return_value = expected_mcp_result

    # Call execute with the dictionary
    result_dict = await mcp_proxy_tool.execute(tool_input_dict)

    # Assert the raw dictionary result returned by execute
    assert result_dict == expected_mcp_result
    mock_mcp_client.call_tool.assert_awaited_once_with(
        server_name="test-server",
        tool_name="test_tool",
        arguments={"arg1": "value1", "arg2": 123},
    )


@pytest.mark.asyncio
async def test_mcp_proxy_tool_execute_client_error_return(mcp_proxy_tool, mock_mcp_client): # Use fixture, test execute
    """Test MCPProxyTool.execute returns error structure from client.call_tool."""
    # Tool input model
    tool_input_model = MCPProxyToolInput(
        server_name="test-server",
        tool_name="error_tool",
        arguments={},
    )
    # Convert model to dict for execute method
    tool_input_dict = tool_input_model.model_dump()

    # Simulate an error response from the MCP client
    error_mcp_result = {"status": "error", "message": "MCP call failed"}
    mock_mcp_client.call_tool.return_value = error_mcp_result

    # Call execute with the dictionary
    result_dict = await mcp_proxy_tool.execute(tool_input_dict)

    # Assert the raw dictionary result returned by execute
    assert result_dict == error_mcp_result
    mock_mcp_client.call_tool.assert_awaited_once_with(
        server_name="test-server",
        tool_name="error_tool",
        arguments={},
    )


@pytest.mark.asyncio
async def test_mcp_proxy_tool_execute_client_exception(mcp_proxy_tool, mock_mcp_client): # Use fixture, test execute
    """Test MCPProxyTool.execute handles exceptions raised by client.call_tool."""
    # Tool input model
    tool_input_model = MCPProxyToolInput(
        server_name="test-server",
        tool_name="exception_tool",
        arguments={},
    )
    # Convert model to dict for execute method
    tool_input_dict = tool_input_model.model_dump()

    mock_mcp_client.call_tool.side_effect = Exception("Network Error")

    # Expect execute to raise a ToolError when the client raises an exception
    with pytest.raises(ToolError) as excinfo:
        await mcp_proxy_tool.execute(tool_input_dict)

    assert "MCP Proxy call failed" in str(excinfo.value)
    assert "Network Error" in str(excinfo.value)
    mock_mcp_client.call_tool.assert_awaited_once_with(
        server_name="test-server",
        tool_name="exception_tool",
        arguments={},
    )


# Test invalid input dictionary structure passed to execute
@pytest.mark.asyncio
async def test_mcp_proxy_tool_execute_invalid_input_dict(mcp_proxy_tool, mock_mcp_client):
    """Test MCPProxyTool.execute with invalid input dict structure."""
    invalid_input_dict = {"server_name": "test", "tool_name": "missing_args"} # Missing 'arguments' key

    # The execute method itself might raise KeyError or similar if accessing missing keys directly
    # Or rely on upstream validation. Here we assume direct access might occur.
    with pytest.raises(KeyError): # Expecting KeyError if 'arguments' is accessed directly
         await mcp_proxy_tool.execute(invalid_input_dict)

    mock_mcp_client.call_tool.assert_not_awaited()
