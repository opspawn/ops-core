#!/usr/bin/env python
"""
MCP Client implementation for ops-core.

Manages connections to multiple configured MCP servers via stdio subprocesses
and routes requests (call_tool, read_resource) to the appropriate server.
"""

import asyncio
import sys
import os
from asyncio import TimeoutError as AsyncTimeoutError # Import TimeoutError specifically
import logging
import subprocess # For process termination
from typing import Optional, List, Dict, Any, Tuple
from contextlib import AsyncExitStack

# MCP SDK Imports
try:
    from mcp import ClientSession, StdioServerParameters, McpError
    from mcp.client.stdio import stdio_client
    # Import base types, but request/response types might be implicitly handled by session methods
    from mcp.types import (
        Tool, Resource, ResourceTemplate,
        TextContent, ImageContent, EmbeddedResource,
        ErrorData # Ensure ErrorData is imported for timeout handling
    )
    # Define expected response types locally if needed for type hinting,
    # otherwise rely on type inference or forward references.
    # For simplicity now, we remove the problematic direct imports.
    # If strict type hinting is needed later, investigate SDK structure further.
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        # Use forward references or Any if specific types aren't easily importable
        # These specific types caused the ImportError
        from mcp.types import (
             CallToolResponse, ReadResourceResponse, ListToolsResponse,
             ListResourcesResponse, ListResourceTemplatesResponse
        )

except ImportError as e:
    logging.error(f"MCP SDK import error: {e}. Please ensure 'mcp' package is installed correctly.")
    raise ImportError(f"MCP SDK import error: {e}. Please ensure 'mcp' package is installed correctly.") from e

# Local config loader import
from ..config.loader import McpConfig, McpServerConfig, get_resolved_mcp_config

# Basic Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OpsMcpClient:
    """
    Manages connections to multiple MCP servers defined in the configuration.
    Starts/stops server subprocesses and routes MCP requests.
    """
    def __init__(self, config: Optional[McpConfig] = None):
        """
        Initializes the multi-server MCP Client.

        Args:
            config: An optional pre-loaded and resolved McpConfig object.
                    If None, the client will attempt to load the default config.
        """
        self._config: McpConfig = config or get_resolved_mcp_config()
        self._sessions: Dict[str, ClientSession] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._transports: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        self._exit_stack = AsyncExitStack()
        self._is_running = False
        logger.info(f"OpsMcpClient initialized with {len(self._config.servers)} servers configured.")

    async def start_all_servers(self):
        """
        Starts all enabled MCP server subprocesses defined in the configuration
        and establishes client sessions.
        """
        if self._is_running:
            logger.warning("Attempted to start servers, but they are already running.")
            return

        logger.info("Starting enabled MCP servers...")
        servers_to_start = {name: conf for name, conf in self._config.servers.items() if conf.enabled}

        if not servers_to_start:
            logger.warning("No enabled MCP servers found in configuration.")
            self._is_running = True # Mark as running even if no servers started
            return

        for name, server_conf in servers_to_start.items():
            try:
                await self._start_server(name, server_conf)
            except Exception as e:
                logger.error(f"Failed to start server '{name}': {e}", exc_info=True)
                # Optionally, decide whether to continue starting others or stop
                # For now, log error and continue

        self._is_running = True
        logger.info(f"Finished starting servers. Active sessions: {list(self._sessions.keys())}")

    async def _start_server(self, name: str, config: McpServerConfig):
        """Starts a single MCP server subprocess and connects to it."""
        logger.info(f"Starting server '{name}'...")

        # Determine absolute script path if relative path is given
        script_path = config.script_path
        if script_path and not os.path.isabs(script_path) and self._config.mcp_server_base_path:
            script_path = os.path.join(self._config.mcp_server_base_path, script_path)
            logger.debug(f"Resolved relative script path for '{name}' to: {script_path}")

        # Validate script path if provided
        if script_path and not os.path.exists(script_path):
             logger.error(f"Script path for server '{name}' not found: {script_path}")
             raise FileNotFoundError(f"Script path for server '{name}' not found: {script_path}")

        # Construct StdioServerParameters
        # Use script_path in args if it exists, otherwise args might be empty or contain other things
        args_list = config.args or []
        if script_path:
            args_list = [script_path] + args_list # Prepend script path if it exists

        server_params = StdioServerParameters(
            command=config.command,
            args=args_list,
            env=config.env or {} # Use resolved env vars
        )

        logger.debug(f"Server '{name}' params: command='{server_params.command}', args={server_params.args}, env={list(server_params.env.keys())}")

        # Use stdio_client context manager via exit_stack
        try:
            # stdio_client now returns a tuple (reader, writer)
            stdio_transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
            reader, writer = stdio_transport
            self._transports[name] = stdio_transport

            # Store the process handle if available (depends on stdio_client implementation details)
            # Note: The mcp.client.stdio.stdio_client doesn't directly expose the process
            # We might need to manage the process separately if fine-grained control is needed.
            # For now, assume the context manager handles process lifetime.
            # If direct process handle is needed, consider using asyncio.create_subprocess_exec directly.

            # Create and initialize the ClientSession
            session = await self._exit_stack.enter_async_context(ClientSession(reader, writer))
            await session.initialize()
            self._sessions[name] = session
            logger.info(f"Server '{name}' started and session initialized.")

        except McpError as mcp_e:
            logger.error(f"MCP Error starting server '{name}': {mcp_e}", exc_info=True)
            # Ensure partial resources are cleaned up if connection fails mid-way
            if name in self._sessions: del self._sessions[name]
            if name in self._transports: del self._transports[name]
            raise # Re-raise to signal failure
        except Exception as e:
            logger.error(f"Unexpected error starting server '{name}': {e}", exc_info=True)
            if name in self._sessions: del self._sessions[name]
            if name in self._transports: del self._transports[name]
            raise # Re-raise to signal failure


    async def stop_all_servers(self):
        """Stops all managed MCP server sessions and associated resources."""
        if not self._is_running:
            logger.warning("Attempted to stop servers, but they are not running.")
            return

        logger.info("Stopping all MCP servers and cleaning up resources...")
        # The AsyncExitStack handles closing sessions and transports started via enter_async_context
        await self._exit_stack.aclose()
        # Clear internal state after stack cleanup
        self._sessions.clear()
        self._transports.clear()
        self._processes.clear() # Clear process dict if it were used
        self._is_running = False
        logger.info("All MCP servers stopped and resources cleaned up.")

    async def get_session(self, server_name: str) -> ClientSession:
        """
        Retrieves the active ClientSession for a given server name.

        Args:
            server_name: The name of the configured server.

        Returns:
            The active ClientSession.

        Raises:
            ValueError: If the server name is not configured, not enabled, or not running.
        """
        if not self._is_running:
             raise RuntimeError("MCP Client is not running. Call start_all_servers() first.")
        if server_name not in self._config.servers:
            raise ValueError(f"MCP server '{server_name}' is not defined in the configuration.")
        if not self._config.servers[server_name].enabled:
             raise ValueError(f"MCP server '{server_name}' is configured but not enabled.")
        if server_name not in self._sessions:
            # This could happen if the server failed to start
            raise ValueError(f"MCP server '{server_name}' is enabled but no active session found (it might have failed to start).")

        return self._sessions[server_name]

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> 'CallToolResponse':
        """
        Calls a tool on the specified MCP server.

        Args:
            server_name: The name of the target MCP server.
            tool_name: The name of the tool to call.
            arguments: The arguments dictionary for the tool.

        Returns:
            The CallToolResponse object from the MCP server.

        Raises:
            ValueError: If the server name is invalid or the session is not active.
            McpError: If the MCP tool call fails.
            Exception: For other unexpected errors.
        """
        logger.info(f"Routing call_tool request: server='{server_name}', tool='{tool_name}', args={arguments}")
        session = await self.get_session(server_name)
        timeout = self._config.mcp_call_tool_timeout_seconds
        logger.debug(f"Using timeout of {timeout} seconds for call_tool on '{server_name}'.")
        try:
            response = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout
            )
            logger.debug(f"call_tool response from '{server_name}': isError={response.isError}, content_types={[type(c).__name__ for c in response.content]}")
            return response
        except AsyncTimeoutError:
            error_msg = f"Timeout ({timeout}s) calling tool '{tool_name}' on server '{server_name}'."
            logger.error(error_msg)
            # Re-raise as an McpError for consistent error handling upstream
            # McpError requires an ErrorData object.
            timeout_error_data = ErrorData(code=-1, message=error_msg) # Use placeholder code
            raise McpError(timeout_error_data) from None # Use 'from None' to avoid chaining the TimeoutError
        except McpError as e:
            logger.error(f"MCP Error calling tool '{tool_name}' on server '{server_name}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling tool '{tool_name}' on server '{server_name}': {e}", exc_info=True)
            raise

    async def read_resource(self, server_name: str, uri: str) -> 'ReadResourceResponse':
        """
        Reads a resource from the specified MCP server.

        Args:
            server_name: The name of the target MCP server.
            uri: The URI of the resource to read.

        Returns:
            The ReadResourceResponse object from the MCP server.

        Raises:
            ValueError: If the server name is invalid or the session is not active.
            McpError: If the MCP resource read fails.
            Exception: For other unexpected errors.
        """
        logger.info(f"Routing read_resource request: server='{server_name}', uri='{uri}'")
        session = await self.get_session(server_name)
        try:
            response = await session.read_resource(uri)
            logger.debug(f"read_resource response from '{server_name}': contents_count={len(response.contents)}")
            return response
        except McpError as e:
            logger.error(f"MCP Error reading resource '{uri}' on server '{server_name}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading resource '{uri}' on server '{server_name}': {e}", exc_info=True)
            raise

    async def list_tools(self, server_name: str) -> 'ListToolsResponse':
        """Lists available tools on the specified MCP server."""
        logger.info(f"Routing list_tools request: server='{server_name}'")
        session = await self.get_session(server_name)
        try:
            response = await session.list_tools()
            logger.debug(f"list_tools response from '{server_name}': tool_count={len(response.tools)}")
            return response
        except McpError as e:
            logger.error(f"MCP Error listing tools on server '{server_name}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing tools on server '{server_name}': {e}", exc_info=True)
            raise

    async def list_resources(self, server_name: str) -> 'ListResourcesResponse':
        """Lists available resources on the specified MCP server."""
        logger.info(f"Routing list_resources request: server='{server_name}'")
        session = await self.get_session(server_name)
        try:
            response = await session.list_resources()
            logger.debug(f"list_resources response from '{server_name}': resource_count={len(response.resources)}")
            return response
        except McpError as e:
            logger.error(f"MCP Error listing resources on server '{server_name}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing resources on server '{server_name}': {e}", exc_info=True)
            raise

    async def list_resource_templates(self, server_name: str) -> 'ListResourceTemplatesResponse':
        """Lists available resource templates on the specified MCP server."""
        logger.info(f"Routing list_resource_templates request: server='{server_name}'")
        session = await self.get_session(server_name)
        try:
            response = await session.list_resource_templates()
            logger.debug(f"list_resource_templates response from '{server_name}': template_count={len(response.resourceTemplates)}")
            return response
        except McpError as e:
            logger.error(f"MCP Error listing resource templates on server '{server_name}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing resource templates on server '{server_name}': {e}", exc_info=True)
            raise

    async def cleanup(self):
        """Cleans up resources by stopping all servers."""
        logger.info("OpsMcpClient cleanup initiated.")
        await self.stop_all_servers()
        logger.info("OpsMcpClient cleanup complete.")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_all_servers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

# Example usage (if run directly, primarily for basic testing)
async def _example_main():
    """Example of using the refactored client."""
    logger.info("Running OpsMcpClient example...")
    # Assumes a valid mcp_servers.yaml exists at the default location
    # and contains at least one enabled server (e.g., 'test-server').
    # You might need to create a dummy server script for this to fully work.

    client = OpsMcpClient()
    try:
        async with client: # Use context manager for start/stop
            logger.info("Client started within context manager.")

            # Example: List tools from a configured server (replace 'test-server' with a valid name)
            server_name_to_test = "test-server" # CHANGE THIS to a server name in your YAML
            if server_name_to_test in client._sessions: # Check if server started successfully
                try:
                    tools_response = await client.list_tools(server_name_to_test)
                    tool_names = [t.name for t in tools_response.tools]
                    logger.info(f"Tools available on '{server_name_to_test}': {tool_names}")

                    # Example: Call a tool if one exists (replace 'example_tool' and args)
                    # if 'example_tool' in tool_names:
                    #     call_response = await client.call_tool(server_name_to_test, 'example_tool', {"param": "value"})
                    #     logger.info(f"Call tool response: {call_response}")

                except (ValueError, McpError) as e:
                    logger.error(f"Error interacting with server '{server_name_to_test}': {e}")
            else:
                 logger.warning(f"Server '{server_name_to_test}' not found or failed to start. Skipping interaction.")

            logger.info("Example interaction finished. Exiting context manager...")

    except FileNotFoundError:
        logger.error("Default MCP configuration file not found. Cannot run example.")
    except Exception as e:
        logger.critical(f"Critical error during example execution: {e}", exc_info=True)

if __name__ == "__main__":
    # Note: Running this directly requires a valid config file and potentially
    # running MCP server scripts. It's primarily for basic structural testing.
    # Use pytest for proper unit/integration testing.
    # asyncio.run(_example_main())
    logger.warning("Running client.py directly is intended for basic checks only. Use pytest for testing.")
    print("This script is intended to be imported as a module. For testing, use pytest.")
