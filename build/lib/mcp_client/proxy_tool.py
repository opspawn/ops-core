# ops_core/mcp_client/proxy_tool.py
"""Defines the MCP Proxy Tool injected into agentkit agents."""

from typing import Any, Dict, Type

from pydantic import BaseModel, Field

# Attempt to import agentkit components. This assumes agentkit is installed
# or available in the Python path where ops-core runs.
try:
    # ToolError is defined in schemas.py
    from agentkit.tools.schemas import Tool, ToolSpec, ToolResult, DEFAULT_SCHEMA, ToolError
except ImportError as e:
    # Provide a more informative error if agentkit isn't found
    raise ImportError(
        "Could not import agentkit. Ensure agentkit package is installed "
        "in the environment where ops-core is running."
    ) from e

# Import the ops-core MCPClient (adjust path if necessary)
# Using a relative import assuming client.py is in the same directory or handled by __init__
from .client import OpsMcpClient # Correct class name


class MCPProxyInput(BaseModel):
    """Input schema for the MCP Proxy Tool."""
    server_name: str = Field(..., description="The target MCP server name (from ops-core config).")
    tool_name: str = Field(..., description="The name of the tool to call on the target MCP server.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the target MCP tool.")
    # Future: Add resource_uri for resource access?


class MCPProxyTool(Tool):
    """
    A special tool injected into agentkit agents by ops-core.
    It proxies calls to external MCP servers via the ops-core MCPClient.
    """
    spec = ToolSpec(
        name="mcp_proxy_tool",
        description=(
            "Calls a specified tool on a connected MCP server. Use this to interact with external "
            "services or data sources managed by ops-core."
        ),
        input_schema=MCPProxyInput,
        output_schema=DEFAULT_SCHEMA,  # Output structure depends on the called MCP tool
    )

    def __init__(self, mcp_client: OpsMcpClient): # Correct type hint
        """
        Initializes the MCPProxyTool.

        Args:
            mcp_client: An instance of the ops-core OpsMcpClient to handle communication.
        """
        if not isinstance(mcp_client, OpsMcpClient): # Correct class check
            # Reason: Ensure the correct client type is provided for functionality.
            raise TypeError("mcp_client must be an instance of ops_core.mcp_client.OpsMcpClient") # Correct class name in error
        self._mcp_client = mcp_client
        super().__init__() # Call parent Tool init if needed

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the proxy call by invoking the ops-core MCPClient.

        Args:
            args: A dictionary matching the MCPProxyInput schema, containing
                  server_name, tool_name, and arguments.

        Returns:
            The result dictionary received from the target MCP tool.

        Raises:
            ToolError: If the MCP call fails or returns an error.
        """
        # Input validation is handled by ToolRegistry/BaseToolManager before this point
        server_name = args["server_name"]
        tool_name = args["tool_name"]
        tool_arguments = args["arguments"]

        print(f"MCPProxyTool: Relaying call to server '{server_name}', tool '{tool_name}' with args: {tool_arguments}")

        try:
            # Use the injected MCPClient instance to make the actual call
            # Assuming mcp_client.call_tool returns the result content directly or raises an error
            result_content = await self._mcp_client.call_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=tool_arguments,
            )
            # The actual result structure varies, return it directly.
            # Agent/Planner needs to interpret this based on the external tool's expected output.
            print(f"MCPProxyTool: Received result: {result_content}")
            return result_content # Return the raw result dictionary/list/value

        except Exception as e:
            # Reason: Catch errors from the MCPClient call and wrap them in ToolError for agentkit.
            error_message = f"MCP Proxy call failed: {type(e).__name__}: {e}"
            print(f"MCPProxyTool: Error - {error_message}")
            # Wrap the exception in ToolError or a specific subclass if needed
            # Returning the error message might be sufficient for the agent planner
            # Alternatively, raise ToolError to ensure it's handled by agent's error logic
            raise ToolError(error_message) from e
