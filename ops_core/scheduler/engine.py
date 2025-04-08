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
from ops_core.models.tasks import Task, TaskStatus
from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError # Removed BaseMetadataStore
import dramatiq # Import dramatiq itself
from ops_core.models.tasks import Task, TaskStatus
from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError # Removed BaseMetadataStore
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.mcp_client.proxy_tool import MCPProxyTool
from ops_core.dependencies import get_metadata_store, get_mcp_client
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
    def __init__(self, metadata_store: InMemoryMetadataStore, mcp_client: Optional[OpsMcpClient] = None):
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
        await self.metadata_store.add_task(new_task)
        logger.debug(f"Task {task_id} added to metadata store.")

        # Dispatch agent tasks to the broker
        if task_type == "agent_run":
            goal = input_data.get("goal", "No goal specified") # Extract goal
            logger.info(f"Dispatching agent task {task_id} to broker with goal: '{goal}'")
            # Send message to the actor
            execute_agent_task_actor.send(task_id=task_id, goal=goal, input_data=input_data)
        else:
            # Handle other task types if necessary (e.g., simple execution, workflows)
            # For now, non-agent tasks remain PENDING unless a worker processes them
            logger.warning(f"Task {task_id} is non-agent type '{task_type}', requires specific worker processing (not implemented).")
            # Optionally, mark as failed or completed if it's a simple task type
            # await self.metadata_store.update_task_status(task_id, TaskStatus.COMPLETED) # Example

        return new_task

    # Removed start/stop methods as they are not needed with Dramatiq


# --- Agent Task Execution Logic ---

async def _run_agent_task_logic(task_id: str, goal: str, input_data: Dict[str, Any]):
    """Helper function containing the core logic for running an agent task."""
    logger.info(f"Starting agent task logic for task_id: {task_id}, goal: {goal}")
    metadata_store = get_metadata_store() # Get store instance via dependency function
    mcp_client = get_mcp_client() # Get MCP client instance

    try:
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

        # Inject MCP Proxy Tool if MCP client is available and running
        if mcp_client and mcp_client._is_running: # Check internal running flag
             try:
                 # MCPProxyTool defines spec as a class attribute, don't pass it to init
                 proxy_tool = MCPProxyTool(mcp_client=mcp_client)
                 tool_registry_instance.add_tool(proxy_tool) # Correct method name is add_tool
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
        agent_result = await agent.run(goal=goal)
        logger.info(f"Agent task {task_id} completed. Result: {agent_result}")

        # --- Update Metadata Store ---
        final_status = TaskStatus.COMPLETED if agent_result.get("status") != "Failed" else TaskStatus.FAILED
        task_result_data = {
            "agent_outcome": agent_result,
            "memory_history": agent.memory.get_history(), # Include memory
        }
        error_message = agent_result.get("reason") if final_status == TaskStatus.FAILED else None

        await metadata_store.update_task_output(
            task_id=task_id,
            result=task_result_data,
            error_message=error_message
        )
        # Explicitly update status after output, as update_task_output might not set final status
        await metadata_store.update_task_status(task_id, final_status)
        logger.info(f"Updated metadata for task {task_id} with status {final_status}")

    except TaskNotFoundError:
        logger.error(f"Task {task_id} not found during agent execution.")
        # Cannot update task if not found
    except Exception as e:
        logger.exception(f"Agent task {task_id} failed with unexpected error: {e}")
        try:
            # Attempt to mark the task as failed in the store
            await metadata_store.update_task_output(
                task_id=task_id,
                result={"error": "Agent execution failed unexpectedly."},
                error_message=str(e)
            )
            await metadata_store.update_task_status(task_id, TaskStatus.FAILED)
        except TaskNotFoundError:
             logger.error(f"Task {task_id} not found when trying to report agent failure.")
        except Exception as store_e:
            logger.exception(f"Failed to update metadata store for failed task {task_id}: {store_e}")

# --- Dramatiq Actor Definition ---

@dramatiq.actor() # Use global decorator, removed store_results option
async def execute_agent_task_actor(task_id: str, goal: str, input_data: Dict[str, Any]):
    """
    Dramatiq actor that executes the agent task logic asynchronously.
    """
    # Load testing hook
    mock_delay_ms_str = os.getenv("OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS")
    if mock_delay_ms_str:
        try:
            delay_ms = int(mock_delay_ms_str)
            logger.warning(f"LOAD TEST MODE: Mocking agent execution with {delay_ms}ms delay for task {task_id}.")
            await asyncio.sleep(delay_ms / 1000.0)
            # Simulate success for load testing
            metadata_store = get_metadata_store()
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
                 metadata_store = get_metadata_store()
                 await metadata_store.update_task_output(task_id=task_id, error_message=f"Mock execution error: {mock_err}")
                 await metadata_store.update_task_status(task_id, TaskStatus.FAILED)
             except Exception:
                 logger.exception(f"Failed to update store after mock execution error for task {task_id}")
             return # Stop execution

    # Call the actual logic
    await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=input_data)
