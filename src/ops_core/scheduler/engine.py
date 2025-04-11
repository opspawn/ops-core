"""
In-memory implementation of the task scheduling engine for Ops Core.

This provides a basic, non-persistent scheduler suitable for development
and testing. It interacts with a metadata store to manage task states.
"""

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, Optional

# Agentkit imports
from agentkit.core.agent import Agent
from agentkit.memory.short_term import ShortTermMemory
from agentkit.planning.placeholder_planner import PlaceholderPlanner # Default/fallback
from agentkit.planning.react_planner import ReActPlanner # Import ReAct
from agentkit.core.interfaces import BaseSecurityManager, BasePlanner, BaseLlmClient
from agentkit.tools.registry import ToolRegistry
# LLM Client imports (add others as needed)
from agentkit.llm_clients.openai_client import OpenAiClient
from agentkit.llm_clients.anthropic_client import AnthropicClient
from agentkit.llm_clients.google_client import GoogleClient
from agentkit.llm_clients.openrouter_client import OpenRouterClient

# Ops-core imports
import dramatiq # Import dramatiq itself
from ops_core.models.tasks import Task, TaskStatus # Corrected path and removed duplicate
from ops_core.metadata.base import BaseMetadataStore # Corrected path
from ops_core.metadata.sql_store import SqlMetadataStore # Corrected path
from ops_core.metadata.store import TaskNotFoundError # Corrected path
from ops_core.mcp_client.client import OpsMcpClient # Corrected path
from ops_core.mcp_client.proxy_tool import MCPProxyTool # Corrected path
# Import session factory and session type for actor
from ops_core.dependencies import async_session_factory, get_mcp_client # Corrected path
from sqlalchemy.ext.asyncio import AsyncSession
# Removed get_metadata_store as actor will create its own
# Removed direct broker import: from ops_core.tasks.broker import broker

logger = logging.getLogger(__name__)

# Default Security Manager (replace with actual implementation if needed)
class DefaultSecurityManager(BaseSecurityManager):
    def check_execution(self, action_type: str, details: Dict[str, Any]) -> bool:
        logger.debug(f"Security check for action '{action_type}': Allowing.")
        return True

    # Implement the missing abstract method
    def check_permissions(self, required_permissions: list[str]) -> bool:
        logger.debug(f"Permission check for '{required_permissions}': Allowing by default.")
        return True

# --- LLM/Planner Instantiation Logic ---

def get_llm_client() -> BaseLlmClient:
    """Instantiates the appropriate LLM client based on environment variables."""
    provider = os.getenv("AGENTKIT_LLM_PROVIDER", "openai").lower()
    # Add API key checks if needed, or assume they are handled by the client itself via env vars
    # api_key = os.getenv(f"{provider.upper()}_API_KEY")
    # if not api_key:
    #     raise ValueError(f"{provider.upper()}_API_KEY environment variable not set.")

    logger.info(f"Instantiating LLM client for provider: {provider}")
    if provider == "openai":
        return OpenAiClient()
    elif provider == "anthropic":
        return AnthropicClient()
    elif provider == "google":
        return GoogleClient()
    elif provider == "openrouter":
        return OpenRouterClient()
    else:
        logger.error(f"Unsupported LLM provider specified: {provider}. Falling back to OpenAI.")
        # Fallback or raise error - let's fallback for now
        return OpenAiClient()

def get_planner(llm_client: BaseLlmClient) -> BasePlanner:
    """Instantiates the appropriate planner, injecting the LLM client."""
    planner_type = os.getenv("AGENTKIT_PLANNER_TYPE", "react").lower()
    model_name = os.getenv("AGENTKIT_LLM_MODEL") # Model might be needed by planner

    logger.info(f"Instantiating planner of type: {planner_type}")
    if planner_type == "react":
        # ReActPlanner only takes the llm_client
        return ReActPlanner(llm_client=llm_client)
    elif planner_type == "placeholder":
        return PlaceholderPlanner()
    else:
        logger.error(f"Unsupported planner type specified: {planner_type}. Falling back to ReAct.")
        # Fallback or raise error
        return ReActPlanner(llm_client=llm_client)


# --- Scheduler Implementation ---

class InMemoryScheduler:
    """
    Basic in-memory task scheduler.

    Uses Dramatiq to dispatch agent tasks for asynchronous execution.
    """
    # Accept mcp_client for test compatibility, even if not directly used here
    # Update type hint to accept any BaseMetadataStore implementation
    def __init__(self, metadata_store: BaseMetadataStore, mcp_client: Optional[OpsMcpClient] = None):
        self.metadata_store = metadata_store
        # self.mcp_client = mcp_client # Store if needed, but actor uses get_mcp_client()
        logger.info("InMemoryScheduler initialized.")
        # No background task loop needed as Dramatiq handles execution

    async def submit_task(self, name: str, task_type: str, input_data: Dict[str, Any]) -> Task:
        """
        Submits a new task to the system.

        Adds the task to the metadata store and dispatches agent tasks
        to the Dramatiq broker.
        """
        task_id = f"task_{uuid.uuid4()}"
        new_task = Task(
            task_id=task_id,
            name=name,
            task_type=task_type,
            input_data=input_data,
            status=TaskStatus.PENDING,
            # created_at/updated_at handled by Pydantic default_factory
        )
        logger.info(f"Submitting task {task_id} ({name}, type: {task_type})")
        # Capture the potentially refreshed task object returned by add_task
        persisted_task = await self.metadata_store.add_task(new_task)
        logger.debug(f"Task {task_id} added to metadata store.")

        # Dispatch agent tasks to the broker
        if task_type == "agent_run":
            goal = input_data.get("goal", "No goal specified") # Extract goal
            logger.info(f"Dispatching agent task {task_id} to broker with goal: '{goal}'")
            # Send message to the actor
            execute_agent_task_actor.send(task_id=task_id, goal=goal, input_data=input_data)
            # logger.warning(f"PHASE 1 REBUILD: execute_agent_task_actor.send() commented out for task {task_id}") # Removed warning
        else:
            # Handle other task types if necessary (e.g., simple execution, workflows)
            # For now, non-agent tasks remain PENDING unless a worker processes them
            logger.warning(f"Task {task_id} is non-agent type '{task_type}', requires specific worker processing (not implemented).")
            # Optionally, mark as failed or completed if it's a simple task type
            # await self.metadata_store.update_task_status(task_id, TaskStatus.COMPLETED) # Example

        # Return the task object that was actually persisted/returned by the store
        return persisted_task

    # Removed start/stop methods as they are not needed with Dramatiq


# --- Agent Task Execution Logic ---

async def _run_agent_task_logic(
    task_id: str,
    goal: str,
    input_data: Dict[str, Any],
    metadata_store: BaseMetadataStore, # Accept store instance
    mcp_client: OpsMcpClient # Accept MCP client instance
):
    """Helper function containing the core logic for running an agent task."""
    logger.info(f"Starting agent task logic for task_id: {task_id}, goal: {goal}")
    # metadata_store and mcp_client are now passed as arguments

    try:
        # Ensure the store is valid before proceeding (basic check)
        if not metadata_store:
             logger.error(f"Metadata store not provided for task {task_id}. Aborting.")
             # Cannot update status without a store
             return

        await metadata_store.update_task_status(task_id, TaskStatus.RUNNING)

        # --- Agent Setup ---
        memory_instance = ShortTermMemory()
        tool_registry_instance = ToolRegistry()
        security_manager_instance = DefaultSecurityManager()

        # Instantiate LLM Client and Planner based on config
        try:
            llm_client_instance = get_llm_client()
            planner_instance = get_planner(llm_client=llm_client_instance)
        except Exception as config_err:
             logger.exception(f"Failed to configure LLM/Planner for task {task_id}: {config_err}")
             await metadata_store.update_task_output(
                 task_id=task_id,
                 result={"error": "Agent configuration failed."},
                 error_message=f"LLM/Planner setup error: {config_err}"
             )
             await metadata_store.update_task_status(task_id, TaskStatus.FAILED)
             return # Stop execution if config fails

        # Inject MCP Proxy Tool if MCP client is available
        # Note: Checking _is_running might be less reliable if client startup is complex.
        # Consider a more robust check or assume it's ready if provided.
        if mcp_client:
             try:
                 proxy_tool = MCPProxyTool(mcp_client=mcp_client)
                 tool_registry_instance.add_tool(proxy_tool)
                 logger.info(f"MCP Proxy Tool injected for task {task_id}")
             except ImportError:
                 logger.warning("MCP Proxy Tool spec not found in agentkit. Skipping injection.")
             except Exception as proxy_err:
                 logger.exception(f"Failed to register MCP Proxy tool for task {task_id}: {proxy_err}")
                 # Decide if this is fatal - maybe just log and continue without proxy?

        agent = Agent(
            memory=memory_instance,
            planner=planner_instance, # Use configured planner
            tool_manager=tool_registry_instance,
            security_manager=security_manager_instance,
        )
        # --- Agent Execution ---
        # logger.warning(f"DEBUG: Skipping agent.run and memory.get_context for task {task_id}") # Restore actual run
        # await asyncio.sleep(0.01) # Maintain minimal async behavior
        agent_result = await agent.run(goal=goal) # Restore actual agent run
        # agent_result = {"status": "Success", "output": "DEBUG: Skipped agent execution"} # Mock result
        logger.info(f"Agent task {task_id} completed. Result: {agent_result}") # Removed DEBUG MODE

        # --- Update Metadata Store ---
        # final_status = TaskStatus.COMPLETED # Assume success in debug mode # Determine status based on result
        memory_content = await agent.memory.get_context() # Restore memory retrieval
        # memory_content = ["DEBUG: Skipped memory retrieval"] # Mock memory
        task_result_data = {
            "agent_outcome": agent_result,
            "memory_history": memory_content, # Include memory
        }
        # Determine status and error message based on agent_result
        # This assumes agent_result is a dict with 'status' and potentially 'error' keys
        # Adjust based on actual Agent.run return type if different
        if isinstance(agent_result, dict) and agent_result.get("status") == "Failed":
            final_status = TaskStatus.FAILED
            error_message = agent_result.get("error", "Agent failed without specific error message.")
        else:
            final_status = TaskStatus.COMPLETED
            error_message = None

        # Update output first (method doesn't take error_message)
        await metadata_store.update_task_output(
            task_id=task_id,
            result=task_result_data
            # Removed error_message=error_message
        )
        # Explicitly update status after output
        await metadata_store.update_task_status(task_id, final_status)
        logger.info(f"Updated metadata for task {task_id} with status {final_status}")

    except TaskNotFoundError:
        logger.error(f"Task {task_id} not found during agent execution.")
        # Cannot update task if not found
    except Exception as e:
        logger.exception(f"Agent task {task_id} failed with unexpected error: {e}")
        if metadata_store: # Check if store is available before trying to update
            try:
                # Attempt to mark the task as failed in the store
                # Update output with error info
                await metadata_store.update_task_output(
                    task_id=task_id,
                    result={"error": "Agent execution failed unexpectedly."}
                )
                # Update status and error message separately
                await metadata_store.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=str(e) # Pass error message here
                )
            except TaskNotFoundError:
                 logger.error(f"Task {task_id} not found when trying to report agent failure.")
            except Exception as store_e:
                logger.exception(f"Failed to update metadata store for failed task {task_id}: {store_e}")
        else:
            logger.error("Metadata store unavailable to report agent failure.")
# --- Dramatiq Actor Definition ---

# Define the core implementation function first
async def _execute_agent_task_actor_impl(task_id: str, goal: str, input_data: Dict[str, Any]):
    """
    Core logic for the Dramatiq actor that executes agent tasks asynchronously.
    Manages its own database session and metadata store instance.
    """
    logger.info(f"Dramatiq actor received task: {task_id}")
    session: Optional[AsyncSession] = None
    metadata_store: Optional[SqlMetadataStore] = None # Use specific type for instantiation

    try:
        # Create a new session for this actor execution
        session = async_session_factory()
        metadata_store = SqlMetadataStore(session)
        mcp_client = get_mcp_client() # Get singleton MCP client

        # --- Load testing hook ---
        mock_delay_ms_str = os.getenv("OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS")
        if mock_delay_ms_str:
            try:
                delay_ms = int(mock_delay_ms_str)
                logger.warning(f"LOAD TEST MODE: Mocking agent execution with {delay_ms}ms delay for task {task_id}.")
                await asyncio.sleep(delay_ms / 1000.0)
                # Simulate success for load testing using the actor's store instance
                await metadata_store.update_task_output(task_id=task_id, result={"mock_result": "load_test_success"})
                await metadata_store.update_task_status(task_id, TaskStatus.COMPLETED)
                logger.info(f"LOAD TEST MODE: Mock agent task {task_id} completed.")
                return # Skip real execution
            except ValueError:
                logger.error(f"Invalid OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS value: {mock_delay_ms_str}. Proceeding with real execution.")
            except Exception as mock_err:
                 logger.exception(f"Error during mock agent execution for task {task_id}: {mock_err}")
                 # Attempt to mark as failed even in mock mode
                 try:
                     await metadata_store.update_task_output(task_id=task_id, error_message=f"Mock execution error: {mock_err}")
                     await metadata_store.update_task_status(task_id, TaskStatus.FAILED)
                 except Exception as store_err_mock:
                     logger.exception(f"Failed to update store after mock execution error for task {task_id}: {store_err_mock}")
                 return # Stop execution

        # --- Call the actual logic ---
        await _run_agent_task_logic(
            task_id=task_id,
            goal=goal,
            input_data=input_data,
            metadata_store=metadata_store,
            mcp_client=mcp_client
        )

    except Exception as actor_err:
        # Catch broad exceptions at the actor level to log failure
        logger.exception(f"Dramatiq actor failed unexpectedly for task {task_id}: {actor_err}")
        # Attempt to mark task as failed if store was initialized
        if metadata_store:
            try:
                # Update output with error info
                await metadata_store.update_task_output(
                    task_id=task_id,
                    result={"error": "Actor execution failed unexpectedly."}
                )
                 # Update status and error message separately
                await metadata_store.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=str(actor_err) # Pass error message here
                )
            except Exception as final_store_err:
                logger.exception(f"Failed to update store after actor-level failure for task {task_id}: {final_store_err}")
    finally:
        # Ensure the session is closed
        if session:
            await session.close()
            logger.debug(f"Database session closed for actor task {task_id}")

# Get the current broker instance to check registry
_broker = dramatiq.get_broker()
_actor_name = "execute_agent_task_actor"

# Only register the actor if it's not already registered
if _actor_name not in _broker.actors:
    # Apply the decorator to the implementation function
    execute_agent_task_actor = dramatiq.actor(_execute_agent_task_actor_impl, actor_name=_actor_name)
else:
    # If already registered (e.g., due to multiple imports), get the existing actor instance
    execute_agent_task_actor = _broker.actors[_actor_name]
